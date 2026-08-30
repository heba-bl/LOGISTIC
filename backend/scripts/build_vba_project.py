"""Compile the VBA modules into `app/assets/vbaProject.bin`, once.

Excel is the only thing that can produce a valid VBA project, and it will only
let a script write one when "Trust access to the VBA project object model" is
enabled - a Trust Center setting, stored per user in the registry, off by
default and off for good reason.

So this script borrows it and gives it back:

    read AccessVBOM  ->  set it to 1  ->  build  ->  restore the original value

The restore runs in a `finally`, so a crash mid-build still puts the setting
back. Nothing else on the machine is touched, and the whole exchange lasts a
few seconds.

The artefact it produces is committed. Everyday rebuilds of the workbook read
that file and need neither Excel nor the setting:

    python scripts/build_vba_project.py       # only when the VBA source changes
    python scripts/generate_operations_xlsm.py  # any time, anywhere
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.vba_source import module_sources  # noqa: E402

ASSET = Path(__file__).resolve().parents[1] / "app" / "assets" / "vbaProject.bin"

#: Where Excel keeps the Trust Center flag, per Office version.
REGISTRY_PARENT = r"Software\Microsoft\Office"
SECURITY_SUBKEY = r"Excel\Security"
VALUE_NAME = "AccessVBOM"
#: `vbext_ct_StdModule`: a plain module, not a class or a form.
STD_MODULE = 1


def _office_versions() -> list[str]:
    import winreg

    versions: list[str] = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PARENT) as parent:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(parent, index)
                except OSError:
                    break
                index += 1
                if name.replace(".", "").isdigit():
                    versions.append(name)
    except OSError:
        pass
    return versions or ["16.0"]


def read_access_vbom(version: str) -> int | None:
    """The current setting, or None when the value is absent (= disabled)."""
    import winreg

    path = rf"{REGISTRY_PARENT}\{version}\{SECURITY_SUBKEY}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return int(value)
    except OSError:
        return None


def write_access_vbom(version: str, value: int | None) -> None:
    """Set the flag, or delete it when `value` is None - restoring "absent"."""
    import winreg

    path = rf"{REGISTRY_PARENT}\{version}\{SECURITY_SUBKEY}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        if value is None:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except OSError:
                pass
        else:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_DWORD, value)


def check_module_visibility() -> None:
    """Refuse to build when one module reads another's private declarations.

    This is not a compiler. It is the one mistake that reached an operator: a
    Private constant in modWorkflow that modSync needed. Under Option Explicit
    that stops the reading module compiling - and VBA compiles a procedure only
    when it first runs, so every test that did not call that exact procedure
    passed, right up to the button click that did.
    """
    import re

    modules = dict(module_sources())
    declared_private: dict[str, str] = {}
    for module, source in modules.items():
        for name in re.findall(r"^Private (?:Const|Function|Sub) (\w+)", source, re.M):
            declared_private[name] = module

    faults = []
    for name, home in sorted(declared_private.items()):
        readers = [
            module
            for module, source in modules.items()
            if module != home and re.search(rf"\b{name}\b", source)
        ]
        if readers:
            faults.append(f"    {name}: Private dans {home}, lu par {', '.join(readers)}")

    if faults:
        raise SystemExit(
            "  Le projet VBA ne compilerait pas:\n"
            + "\n".join(faults)
            + "\n  Passez ces declarations en Public."
        )

    check_reserved_names(modules)
    print(f"  {len(modules)} modules: portee et noms de variables verifies")


#: Members of the Excel object model that a standard module can reach with no
#: qualifier. A local of the same name shadows one of these, and VBA resolves the
#: collision its own way - `names = Array(...)` became an assignment to
#: Application.Names and raised error 450.
EXCEL_GLOBALS = frozenset(
    """rows columns cells names sheets range selection count value application
    workbooks worksheets activesheet activecell thisworkbook activeworkbook
    union intersect error date time now""".split()
)


def check_reserved_names(modules: dict[str, str]) -> None:
    """Refuse to build on a variable named after an Excel global."""
    import re

    faults = []
    for module, source in modules.items():
        for number, line in enumerate(source.splitlines(), 1):
            declaration = re.match(r"\s*(?:Dim|Static)\s+(.*)", line)
            if not declaration:
                continue
            for part in declaration.group(1).split(","):
                tokens = part.strip().split()
                if tokens and tokens[0].lower() in EXCEL_GLOBALS:
                    faults.append(f"    {module} ligne {number}: {tokens[0]}")

        for signature in re.finditer(
            r"^(?:Public |Private )?(?:Sub|Function) (\w+)\(([^)]*)\)", source, re.M
        ):
            for part in signature.group(2).split(","):
                tokens = (
                    part.replace("ByVal", "").replace("ByRef", "")
                    .replace("Optional", "").strip().split()
                )
                if tokens and tokens[0].lower() in EXCEL_GLOBALS:
                    faults.append(
                        f"    {module} {signature.group(1)}: parametre {tokens[0]}"
                    )

    if faults:
        raise SystemExit(
            "  Des variables portent un nom appartenant a Excel:\n"
            + "\n".join(faults)
            + "\n  Renommez-les: VBA les resout contre l'objet Excel, pas contre"
            " la declaration locale."
        )


def build_with_excel(target: Path) -> None:
    """Have Excel create a macro workbook carrying our modules."""
    import win32com.client

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        workbook = excel.Workbooks.Add()
        project = workbook.VBProject

        for name, source in module_sources():
            component = project.VBComponents.Add(STD_MODULE)
            component.Name = name
            component.CodeModule.AddFromString(source)
            print(f"  module {name:14} {len(source.splitlines()):>4} lignes")

        # 52 = xlOpenXMLWorkbookMacroEnabled
        workbook.SaveAs(str(target), FileFormat=52)
        workbook.Close(SaveChanges=False)
    finally:
        excel.Quit()


def extract_vba(xlsm: Path, destination: Path) -> int:
    with zipfile.ZipFile(xlsm) as archive:
        payload = archive.read("xl/vbaProject.bin")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return len(payload)


def main() -> int:
    check_module_visibility()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-setting",
        action="store_true",
        help="ne pas restaurer AccessVBOM (deconseille)",
    )
    args = parser.parse_args()

    if sys.platform != "win32":
        print("Ce script exige Excel sous Windows.", file=sys.stderr)
        return 2

    version = _office_versions()[0]
    original = read_access_vbom(version)
    print(f"Office {version} — AccessVBOM avant: {original if original is not None else 'absent'}")

    workdir = Path(tempfile.mkdtemp(prefix="slcc-vba-"))
    try:
        write_access_vbom(version, 1)
        print("  reglage active temporairement")

        target = workdir / "carrier.xlsm"
        build_with_excel(target)
        size = extract_vba(target, ASSET)
        print(f"\n  {ASSET.relative_to(Path.cwd()) if ASSET.is_relative_to(Path.cwd()) else ASSET}")
        print(f"  vbaProject.bin extrait: {size:,} octets")
        return 0
    except Exception as error:  # noqa: BLE001
        print(f"ECHEC: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_setting:
            write_access_vbom(version, original)
            restored = read_access_vbom(version)
            print(
                f"  reglage restaure: {restored if restored is not None else 'absent'}"
                f" (valeur d'origine: {original if original is not None else 'absent'})"
            )
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
