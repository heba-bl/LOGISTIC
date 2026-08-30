"""Deterministic generator for the demonstration vehicle nomenclature.

SYNTHETIC DATA - built for the demonstration. It is not, and must never be
presented as, real company data.

The nomenclature is not random: it is built the way an industrial BOM is built,
system by system. Each of the 15 systems owns a set of subsystems, each subsystem
owns component families, and each family declines into realistic variants
(positions, sides, sizes). The result is ~2 400 coherent references.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

#: Fixed seed: the nomenclature is identical on every run, so the demonstration
#: and the Excel files are reproducible.
SEED = 20260820

VEHICLE = {
    "code": "SLCC-X1",
    "name": "SLCC X1",
    "segment": "Compact SUV (synthetic)",
    "model_year": 2026,
    "description": (
        "Synthetic vehicle used for the SLCC demonstration. The nomenclature "
        "below is generated data and does not describe a real product."
    ),
}


@dataclass(frozen=True)
class Family:
    """A component family and how it declines into references."""

    name: str
    #: Variant qualifiers appended to the description.
    variants: tuple[str, ...]
    size: str  # SMALL | LARGE
    #: Typical quantity fitted per vehicle, as a (min, max) range.
    quantity: tuple[int, int]
    #: Optional second axis. Fasteners exist per diameter AND per length, wiring
    #: per gauge AND per colour - this is what makes a real BOM large.
    cross: tuple[str, ...] = ()
    #: When False the family is common to every configuration (no trim/engine
    #: declination), which is the case for structural and safety parts.
    declined: bool = True


@dataclass(frozen=True)
class Subsystem:
    name: str
    families: tuple[Family, ...]


@dataclass(frozen=True)
class System:
    code: str
    label: str
    category: str
    subsystems: tuple[Subsystem, ...]
    #: Configuration axis the system varies on. A vehicle carries a different
    #: part number per trim level or per engine, exactly as in a real BOM.
    declinations: tuple[str, ...] = ()


#: Configuration axes.
TRIM_LEVELS = ("finition Access", "finition Confort", "finition Premium")
ENGINES = ("essence 1.2 T", "essence 1.6 T", "diesel 1.5 D")
GRADES = ("execution A", "execution B", "execution C")
PLATINGS = ("etame", "dore", "nickele")
DIAMETERS = ("D3", "D4", "D5")
KEYINGS = ("detrompeur A", "detrompeur B", "detrompeur C")
FINISHES = ("zingue", "noir", "inox")


SIDES = ("avant gauche", "avant droit", "arriere gauche", "arriere droit")
FRONT_REAR = ("avant", "arriere")
LEFT_RIGHT = ("gauche", "droit")
SIZES_MM = ("M6", "M8", "M10", "M12", "M14")
LENGTHS = ("20 mm", "25 mm", "30 mm", "40 mm", "50 mm", "65 mm", "80 mm")
GAUGES = ("0.35 mm2", "0.5 mm2", "0.75 mm2", "1.0 mm2", "1.5 mm2", "2.5 mm2", "4.0 mm2")
COLOURS = ("noir", "gris", "beige", "anthracite")
TRIMS = ("entree de gamme", "confort", "premium")

#: How each system declines per vehicle configuration. Interior and comfort
#: parts change with the trim level, powertrain parts with the engine, structural
#: parts only through an engineering execution index.
SYSTEM_DECLINATIONS: dict[str, tuple[str, ...]] = {
    "BRK": GRADES,
    "SUS": GRADES,
    "STE": GRADES,
    "PWT": ENGINES,
    "TRA": ENGINES,
    "ELE": GRADES,
    "BOD": GRADES,
    "EXT": TRIM_LEVELS,
    "INT": TRIM_LEVELS,
    "HVA": TRIM_LEVELS,
    "LIG": TRIM_LEVELS,
    "FUE": ENGINES,
    "EXH": ENGINES,
    "SAF": GRADES,
    "CHS": GRADES,
}

SYSTEMS: tuple[System, ...] = (
    System(
        "BRK",
        "Freinage",
        "Freinage",
        (
            Subsystem(
                "Freins a disque",
                (
                    Family("Etrier de frein", SIDES, "LARGE", (1, 1)),
                    Family("Disque de frein", FRONT_REAR, "LARGE", (2, 2)),
                    Family("Plaquette de frein", FRONT_REAR, "SMALL", (4, 4)),
                    Family("Support d'etrier", SIDES, "LARGE", (1, 1)),
                    Family("Vis d'etrier", SIZES_MM, "SMALL", (4, 8), cross=LENGTHS, declined=False),
                    Family("Ressort de plaquette", FRONT_REAR, "SMALL", (2, 4)),
                    Family("Cache-poussiere d'etrier", SIDES, "SMALL", (1, 2)),
                ),
            ),
            Subsystem(
                "Circuit hydraulique",
                (
                    Family("Flexible de frein", SIDES, "SMALL", (1, 1)),
                    Family("Tube de frein rigide", ("primaire", "secondaire", "arriere"), "SMALL", (1, 2)),
                    Family("Maitre-cylindre", ("standard", "renforce"), "LARGE", (1, 1)),
                    Family("Reservoir de liquide", ("standard",), "SMALL", (1, 1)),
                    Family("Raccord hydraulique", SIZES_MM, "SMALL", (2, 6), cross=DIAMETERS, declined=False),
                    Family("Bloc ABS", ("4 canaux", "4 canaux ESP"), "LARGE", (1, 1)),
                ),
            ),
            Subsystem(
                "Frein de stationnement",
                (
                    Family("Cable de frein a main", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Levier de frein a main", ("mecanique", "electrique"), "LARGE", (1, 1)),
                    Family("Actionneur EPB", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Contacteur de frein", ("standard",), "SMALL", (1, 2)),
                ),
            ),
        ),
    ),
    System(
        "SUS",
        "Suspension",
        "Chassis",
        (
            Subsystem(
                "Suspension avant",
                (
                    Family("Amortisseur avant", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Ressort helicoidal avant", TRIMS, "LARGE", (1, 1)),
                    Family("Coupelle superieure", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Butee de suspension", LEFT_RIGHT, "SMALL", (1, 2)),
                    Family("Bras de suspension", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Rotule de suspension", LEFT_RIGHT, "SMALL", (1, 2)),
                    Family("Silentbloc de bras", ("avant", "arriere"), "SMALL", (2, 4)),
                    Family("Barre stabilisatrice avant", TRIMS, "LARGE", (1, 1)),
                    Family("Biellette de barre", LEFT_RIGHT, "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Suspension arriere",
                (
                    Family("Amortisseur arriere", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Ressort helicoidal arriere", TRIMS, "LARGE", (1, 1)),
                    Family("Traverse arriere", ("standard", "renforcee"), "LARGE", (1, 1)),
                    Family("Bras tire arriere", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Silentbloc arriere", ("superieur", "inferieur"), "SMALL", (2, 4)),
                    Family("Butee de compression", LEFT_RIGHT, "SMALL", (1, 2)),
                ),
            ),
            Subsystem(
                "Moyeux et roulements",
                (
                    Family("Moyeu de roue", SIDES, "LARGE", (1, 1)),
                    Family("Roulement de roue", FRONT_REAR, "SMALL", (2, 2)),
                    Family("Ecrou de moyeu", SIZES_MM, "SMALL", (1, 4), cross=FINISHES, declined=False),
                    Family("Porte-fusee", LEFT_RIGHT, "LARGE", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "STE",
        "Direction",
        "Chassis",
        (
            Subsystem(
                "Colonne de direction",
                (
                    Family("Colonne de direction", ("reglable", "fixe"), "LARGE", (1, 1)),
                    Family("Cardan de direction", ("superieur", "inferieur"), "SMALL", (1, 1)),
                    Family("Contacteur tournant", ("standard",), "SMALL", (1, 1)),
                    Family("Verrou antivol", ("mecanique", "electronique"), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Cremaillere",
                (
                    Family("Cremaillere de direction", ("assistee", "electrique"), "LARGE", (1, 1)),
                    Family("Biellette de direction", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Rotule axiale", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Soufflet de cremaillere", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Moteur d'assistance", ("standard", "renforce"), "LARGE", (1, 1)),
                ),
            ),
            Subsystem(
                "Volant",
                (
                    Family("Volant", TRIMS, "LARGE", (1, 1)),
                    Family("Commande au volant", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Airbag conducteur", ("standard",), "LARGE", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "PWT",
        "Groupe motopropulseur",
        "Motorisation",
        (
            Subsystem(
                "Bloc moteur",
                (
                    Family("Carter d'huile", ("aluminium", "acier"), "LARGE", (1, 1)),
                    Family("Joint de carter", ("standard",), "SMALL", (1, 1)),
                    Family("Bougie d'allumage", ("iridium", "platine"), "SMALL", (3, 4), cross=("court", "long")),
                    Family("Bobine d'allumage", ("cylindre 1", "cylindre 2", "cylindre 3", "cylindre 4"), "SMALL", (1, 1)),
                    Family("Injecteur", ("cylindre 1", "cylindre 2", "cylindre 3", "cylindre 4"), "SMALL", (1, 1)),
                    Family("Courroie accessoires", ("standard", "renforcee"), "SMALL", (1, 1)),
                    Family("Galet tendeur", ("fixe", "automatique"), "SMALL", (1, 2)),
                    Family("Pompe a eau", ("mecanique", "electrique"), "LARGE", (1, 1)),
                    Family("Thermostat", ("82 C", "88 C"), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Admission",
                (
                    Family("Collecteur d'admission", ("plastique", "aluminium"), "LARGE", (1, 1)),
                    Family("Filtre a air", ("papier", "haute performance"), "SMALL", (1, 1)),
                    Family("Boitier papillon", ("electronique",), "SMALL", (1, 1)),
                    Family("Durite d'admission", ("amont", "aval"), "SMALL", (1, 2)),
                    Family("Debitmetre d'air", ("standard",), "SMALL", (1, 1)),
                    Family("Turbocompresseur", ("simple", "geometrie variable"), "LARGE", (1, 1)),
                    Family("Echangeur air-air", ("standard", "renforce"), "LARGE", (1, 1)),
                ),
            ),
            Subsystem(
                "Supports moteur",
                (
                    Family("Support moteur", ("gauche", "droit", "arriere"), "LARGE", (1, 1)),
                    Family("Silentbloc moteur", ("hydraulique", "caoutchouc"), "SMALL", (1, 2)),
                    Family("Vis de support", SIZES_MM, "SMALL", (4, 8), cross=LENGTHS, declined=False),
                ),
            ),
        ),
    ),
    System(
        "TRA",
        "Transmission",
        "Motorisation",
        (
            Subsystem(
                "Boite de vitesses",
                (
                    Family("Carter de boite", ("manuelle 6", "automatique 7"), "LARGE", (1, 1)),
                    Family("Fourchette de selection", ("1-2", "3-4", "5-6"), "SMALL", (1, 1)),
                    Family("Synchroniseur", ("1-2", "3-4", "5-6"), "SMALL", (1, 1)),
                    Family("Joint de sortie de boite", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Cable de commande", ("selection", "passage"), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Embrayage",
                (
                    Family("Disque d'embrayage", ("standard", "renforce"), "LARGE", (1, 1)),
                    Family("Mecanisme d'embrayage", ("standard",), "LARGE", (1, 1)),
                    Family("Butee d'embrayage", ("hydraulique", "mecanique"), "SMALL", (1, 1)),
                    Family("Emetteur d'embrayage", ("standard",), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Transmission de roue",
                (
                    Family("Arbre de transmission", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Soufflet de cardan", ("cote roue", "cote boite"), "SMALL", (1, 2)),
                    Family("Roulement de cardan", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Collier de soufflet", ("petit", "grand"), "SMALL", (2, 4), cross=DIAMETERS, declined=False),
                ),
            ),
        ),
    ),
    System(
        "ELE",
        "Electrique",
        "Electrique",
        (
            Subsystem(
                "Faisceaux",
                (
                    Family("Faisceau principal", ("planche de bord", "moteur", "habitacle"), "LARGE", (1, 1)),
                    Family("Faisceau de porte", SIDES, "LARGE", (1, 1)),
                    Family("Faisceau de hayon", ("standard",), "LARGE", (1, 1)),
                    Family("Cable unitaire", GAUGES, "SMALL", (4, 20), cross=COLOURS, declined=False),
                    Family("Passe-fil", ("porte", "tablier", "hayon"), "SMALL", (2, 6), cross=DIAMETERS, declined=False),
                ),
            ),
            Subsystem(
                "Connectique",
                (
                    Family("Connecteur 2 voies", COLOURS, "SMALL", (6, 20), cross=KEYINGS, declined=False),
                    Family("Connecteur 4 voies", COLOURS, "SMALL", (6, 18), cross=KEYINGS, declined=False),
                    Family("Connecteur 8 voies", COLOURS, "SMALL", (4, 12), cross=KEYINGS, declined=False),
                    Family("Connecteur 12 voies", COLOURS, "SMALL", (2, 8), cross=KEYINGS, declined=False),
                    Family("Contact serti", GAUGES, "SMALL", (20, 60), cross=PLATINGS, declined=False),
                    Family("Joint de connecteur", ("2 voies", "4 voies", "8 voies"), "SMALL", (6, 20), cross=COLOURS, declined=False),
                    Family("Verrou secondaire", ("2 voies", "4 voies", "8 voies"), "SMALL", (4, 12), cross=KEYINGS, declined=False),
                ),
            ),
            Subsystem(
                "Distribution electrique",
                (
                    Family("Boitier a fusibles", ("moteur", "habitacle"), "LARGE", (1, 1)),
                    Family("Fusible", ("5 A", "10 A", "15 A", "20 A", "30 A", "40 A"), "SMALL", (4, 12), declined=False),
                    Family("Relais", ("4 broches", "5 broches"), "SMALL", (2, 8), cross=("12 V", "24 V"), declined=False),
                    Family("Batterie", ("60 Ah", "70 Ah", "80 Ah"), "LARGE", (1, 1)),
                    Family("Cosse de batterie", ("plus", "moins"), "SMALL", (1, 1)),
                    Family("Alternateur", ("110 A", "150 A"), "LARGE", (1, 1)),
                    Family("Demarreur", ("standard", "stop-start"), "LARGE", (1, 1)),
                ),
            ),
            Subsystem(
                "Calculateurs",
                (
                    Family("Calculateur moteur", ("essence", "diesel"), "LARGE", (1, 1)),
                    Family("Calculateur de carrosserie", ("standard",), "LARGE", (1, 1)),
                    Family("Module de porte", SIDES, "SMALL", (1, 1)),
                    Family("Capteur de position", ("vilebrequin", "arbre a cames", "papillon"), "SMALL", (1, 2)),
                    Family("Capteur de temperature", ("eau", "air", "huile"), "SMALL", (1, 2)),
                    Family("Capteur ABS", SIDES, "SMALL", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "BOD",
        "Carrosserie",
        "Carrosserie",
        (
            Subsystem(
                "Structure",
                (
                    Family("Longeron", SIDES, "LARGE", (1, 1)),
                    Family("Traverse de plancher", ("avant", "centrale", "arriere"), "LARGE", (1, 1)),
                    Family("Renfort de pied milieu", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Berceau moteur", ("acier", "aluminium"), "LARGE", (1, 1)),
                    Family("Absorbeur de choc", FRONT_REAR, "LARGE", (1, 2)),
                ),
            ),
            Subsystem(
                "Ouvrants",
                (
                    Family("Porte", SIDES, "LARGE", (1, 1)),
                    Family("Charniere de porte", ("superieure", "inferieure"), "SMALL", (2, 2)),
                    Family("Serrure de porte", SIDES, "SMALL", (1, 1)),
                    Family("Leve-vitre", SIDES, "LARGE", (1, 1)),
                    Family("Capot", ("acier", "aluminium"), "LARGE", (1, 1)),
                    Family("Hayon", ("tole", "composite"), "LARGE", (1, 1)),
                    Family("Verin de hayon", LEFT_RIGHT, "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Fixations carrosserie",
                (
                    Family("Vis de carrosserie", SIZES_MM, "SMALL", (10, 40), cross=LENGTHS, declined=False),
                    Family("Ecrou cage", SIZES_MM, "SMALL", (8, 30), cross=FINISHES, declined=False),
                    Family("Rivet aveugle", LENGTHS, "SMALL", (10, 50), cross=DIAMETERS, declined=False),
                    Family("Agrafe plastique", ("standard", "renforcee"), "SMALL", (20, 60), cross=COLOURS, declined=False),
                    Family("Goujon soude", SIZES_MM, "SMALL", (6, 24), cross=LENGTHS, declined=False),
                ),
            ),
        ),
    ),
    System(
        "EXT",
        "Exterieur",
        "Carrosserie",
        (
            Subsystem(
                "Pare-chocs",
                (
                    Family("Peau de pare-chocs", FRONT_REAR, "LARGE", (1, 1)),
                    Family("Grille de calandre", TRIMS, "LARGE", (1, 1)),
                    Family("Support de pare-chocs", SIDES, "SMALL", (1, 1)),
                    Family("Bavette", SIDES, "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Vitrage",
                (
                    Family("Pare-brise", ("standard", "athermique", "chauffant"), "LARGE", (1, 1)),
                    Family("Vitre de porte", SIDES, "LARGE", (1, 1)),
                    Family("Lunette arriere", ("standard", "degivrante"), "LARGE", (1, 1)),
                    Family("Joint de vitrage", SIDES, "SMALL", (1, 2)),
                ),
            ),
            Subsystem(
                "Retroviseurs et essuyage",
                (
                    Family("Retroviseur exterieur", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Coque de retroviseur", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Bras d'essuie-glace", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Balai d'essuie-glace", ("conducteur", "passager", "arriere"), "SMALL", (1, 1)),
                    Family("Moteur d'essuie-glace", FRONT_REAR, "LARGE", (1, 1)),
                    Family("Gicleur de lave-glace", LEFT_RIGHT, "SMALL", (1, 2)),
                ),
            ),
        ),
    ),
    System(
        "INT",
        "Interieur",
        "Interieur",
        (
            Subsystem(
                "Planche de bord",
                (
                    Family("Planche de bord", TRIMS, "LARGE", (1, 1)),
                    Family("Combine d'instruments", ("analogique", "numerique"), "LARGE", (1, 1)),
                    Family("Buse d'aeration", ("centrale", "laterale gauche", "laterale droite"), "SMALL", (1, 2)),
                    Family("Boite a gants", ("standard", "refrigeree"), "LARGE", (1, 1)),
                    Family("Console centrale", TRIMS, "LARGE", (1, 1)),
                ),
            ),
            Subsystem(
                "Sieges",
                (
                    Family("Armature de siege", ("conducteur", "passager", "banquette"), "LARGE", (1, 1)),
                    Family("Mousse d'assise", ("conducteur", "passager", "banquette"), "LARGE", (1, 1)),
                    Family("Coiffe de siege", COLOURS, "LARGE", (1, 2)),
                    Family("Glissiere de siege", LEFT_RIGHT, "SMALL", (1, 2)),
                    Family("Appui-tete", ("avant", "arriere"), "SMALL", (2, 3)),
                    Family("Moteur de reglage", ("longitudinal", "hauteur", "dossier"), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Garnissage",
                (
                    Family("Panneau de porte", SIDES, "LARGE", (1, 1)),
                    Family("Garniture de pavillon", TRIMS, "LARGE", (1, 1)),
                    Family("Tapis de sol", COLOURS, "SMALL", (1, 4)),
                    Family("Insonorisant", ("tablier", "plancher", "passage de roue"), "LARGE", (1, 2)),
                    Family("Enjoliveur de seuil", SIDES, "SMALL", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "HVA",
        "Climatisation",
        "Confort",
        (
            Subsystem(
                "Circuit frigorifique",
                (
                    Family("Compresseur de climatisation", ("mecanique", "electrique"), "LARGE", (1, 1)),
                    Family("Condenseur", ("standard", "renforce"), "LARGE", (1, 1)),
                    Family("Evaporateur", ("standard",), "LARGE", (1, 1)),
                    Family("Detendeur", ("standard",), "SMALL", (1, 1)),
                    Family("Tuyau de climatisation", ("haute pression", "basse pression"), "SMALL", (1, 2)),
                    Family("Pressostat", ("standard",), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Distribution d'air",
                (
                    Family("Groupe de ventilation", ("standard", "bizone"), "LARGE", (1, 1)),
                    Family("Pulseur d'air", ("standard", "renforce"), "LARGE", (1, 1)),
                    Family("Filtre habitacle", ("papier", "charbon actif"), "SMALL", (1, 1)),
                    Family("Volet de mixage", ("chaud", "froid", "recyclage"), "SMALL", (1, 2)),
                    Family("Conduit d'air", ("central", "lateral", "arriere"), "SMALL", (1, 3)),
                    Family("Radiateur de chauffage", ("standard",), "LARGE", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "LIG",
        "Eclairage",
        "Electrique",
        (
            Subsystem(
                "Eclairage avant",
                (
                    Family("Projecteur", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Module LED", ("croisement", "route", "diurne"), "SMALL", (1, 2)),
                    Family("Correcteur de site", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Antibrouillard avant", LEFT_RIGHT, "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Eclairage arriere",
                (
                    Family("Feu arriere", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Troisieme feu stop", ("standard",), "SMALL", (1, 1)),
                    Family("Feu de plaque", LEFT_RIGHT, "SMALL", (1, 1)),
                    Family("Catadioptre", LEFT_RIGHT, "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Eclairage interieur",
                (
                    Family("Plafonnier", ("avant", "arriere"), "SMALL", (1, 1)),
                    Family("Liseuse", LEFT_RIGHT, "SMALL", (1, 2)),
                    Family("Eclairage de coffre", ("standard",), "SMALL", (1, 1)),
                    Family("Eclairage d'ambiance", COLOURS, "SMALL", (2, 6)),
                ),
            ),
        ),
    ),
    System(
        "FUE",
        "Carburant",
        "Motorisation",
        (
            Subsystem(
                "Reservoir",
                (
                    Family("Reservoir de carburant", ("50 L", "60 L"), "LARGE", (1, 1)),
                    Family("Pompe a carburant", ("immergee", "externe"), "SMALL", (1, 1)),
                    Family("Jauge de carburant", ("standard",), "SMALL", (1, 1)),
                    Family("Bouchon de reservoir", ("a cle", "sans cle"), "SMALL", (1, 1)),
                    Family("Goulotte de remplissage", ("essence", "diesel"), "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Alimentation",
                (
                    Family("Filtre a carburant", ("standard", "avec decanteur"), "SMALL", (1, 1)),
                    Family("Rampe d'injection", ("standard", "haute pression"), "SMALL", (1, 1)),
                    Family("Tuyau de carburant", ("aller", "retour"), "SMALL", (1, 2)),
                    Family("Regulateur de pression", ("standard",), "SMALL", (1, 1)),
                    Family("Canister", ("standard",), "SMALL", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "EXH",
        "Echappement",
        "Motorisation",
        (
            Subsystem(
                "Ligne d'echappement",
                (
                    Family("Collecteur d'echappement", ("fonte", "acier"), "LARGE", (1, 1)),
                    Family("Catalyseur", ("primaire", "secondaire"), "LARGE", (1, 1)),
                    Family("Filtre a particules", ("standard",), "LARGE", (1, 1)),
                    Family("Silencieux", ("intermediaire", "arriere"), "LARGE", (1, 1)),
                    Family("Tube d'echappement", ("avant", "intermediaire", "arriere"), "LARGE", (1, 1)),
                    Family("Collier d'echappement", SIZES_MM, "SMALL", (2, 6), cross=DIAMETERS, declined=False),
                    Family("Silentbloc d'echappement", ("avant", "arriere"), "SMALL", (2, 4)),
                    Family("Sonde lambda", ("amont", "aval"), "SMALL", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "SAF",
        "Securite",
        "Securite",
        (
            Subsystem(
                "Retenue",
                (
                    Family("Ceinture de securite", SIDES, "LARGE", (1, 1)),
                    Family("Enrouleur de ceinture", SIDES, "SMALL", (1, 1)),
                    Family("Pretensionneur", SIDES, "SMALL", (1, 1)),
                    Family("Boucle de ceinture", SIDES, "SMALL", (1, 1)),
                    Family("Fixation Isofix", LEFT_RIGHT, "SMALL", (1, 2)),
                ),
            ),
            Subsystem(
                "Airbags",
                (
                    Family("Airbag passager", ("standard",), "LARGE", (1, 1)),
                    Family("Airbag lateral", SIDES, "SMALL", (1, 1)),
                    Family("Airbag rideau", LEFT_RIGHT, "LARGE", (1, 1)),
                    Family("Calculateur airbag", ("standard",), "SMALL", (1, 1)),
                    Family("Capteur de choc", SIDES, "SMALL", (1, 1)),
                ),
            ),
            Subsystem(
                "Aides a la conduite",
                (
                    Family("Camera de recul", ("standard", "haute definition"), "SMALL", (1, 1)),
                    Family("Radar de stationnement", SIDES, "SMALL", (1, 2)),
                    Family("Camera frontale", ("standard",), "SMALL", (1, 1)),
                    Family("Radar avant", ("standard",), "LARGE", (1, 1)),
                ),
            ),
        ),
    ),
    System(
        "CHS",
        "Chassis et roues",
        "Chassis",
        (
            Subsystem(
                "Roues",
                (
                    Family("Jante", ("16 pouces", "17 pouces", "18 pouces"), "LARGE", (4, 5)),
                    Family("Pneumatique", ("205/55 R16", "215/50 R17", "225/45 R18"), "LARGE", (4, 5)),
                    Family("Ecrou de roue", SIZES_MM, "SMALL", (16, 20), cross=FINISHES, declined=False),
                    Family("Enjoliveur", ("16 pouces", "17 pouces"), "SMALL", (4, 4)),
                    Family("Valve de gonflage", ("standard", "avec capteur"), "SMALL", (4, 5)),
                ),
            ),
            Subsystem(
                "Protection sous caisse",
                (
                    Family("Bouclier sous moteur", ("plastique", "aluminium"), "LARGE", (1, 1)),
                    Family("Passage de roue", SIDES, "LARGE", (1, 1)),
                    Family("Protection de reservoir", ("standard",), "LARGE", (1, 1)),
                    Family("Agrafe de protection", ("standard", "renforcee"), "SMALL", (10, 30), cross=COLOURS, declined=False),
                ),
            ),
        ),
    ),
)

#: Consumables and fixings. Common to every configuration (``declined=False``)
#: but declined by dimension, which is what makes them numerous in a real BOM.
CONSUMABLE_SUBSYSTEMS: dict[str, tuple[Subsystem, ...]] = {
    "ELE": (
        Subsystem(
            "Protection de faisceau",
            (
                Family("Gaine annelee", DIAMETERS, "SMALL", (4, 12), cross=COLOURS, declined=False),
                Family("Ruban adhesif faisceau", ("19 mm", "25 mm", "32 mm"), "SMALL", (6, 20),
                       cross=("tissu", "PVC", "mousse"), declined=False),
                Family("Collier de faisceau", SIZES_MM, "SMALL", (10, 40), cross=COLOURS, declined=False),
                Family("Manchon thermoretractable", DIAMETERS, "SMALL", (4, 16), cross=COLOURS, declined=False),
                Family("Passe-cloison", DIAMETERS, "SMALL", (2, 8), cross=FINISHES, declined=False),
            ),
        ),
        Subsystem(
            "Masse et protection electrique",
            (
                Family("Cosse de masse", GAUGES, "SMALL", (2, 8), cross=DIAMETERS, declined=False),
                Family("Fusible maxi", ("50 A", "60 A", "80 A", "100 A"), "SMALL", (1, 4),
                       cross=("boulonne", "enfichable"), declined=False),
                Family("Porte-fusible", ("1 voie", "2 voies", "4 voies"), "SMALL", (1, 3),
                       cross=("etanche", "standard"), declined=False),
            ),
        ),
    ),
    "INT": (
        Subsystem(
            "Fixation d'habillage",
            (
                Family("Vis de garnissage", SIZES_MM, "SMALL", (12, 36), cross=FINISHES, declined=False),
                Family("Clip de panneau", COLOURS, "SMALL", (16, 48), cross=DIAMETERS, declined=False),
                Family("Agrafe de tapis", ("standard", "renforcee"), "SMALL", (8, 20),
                       cross=COLOURS, declined=False),
            ),
        ),
    ),
    "BOD": (
        Subsystem(
            "Etancheite",
            (
                Family("Joint de porte", SIDES, "SMALL", (1, 1), cross=("primaire", "secondaire")),
                Family("Mastic d etancheite", ("cordon", "extrude", "pulverise"), "SMALL", (2, 6),
                       cross=DIAMETERS, declined=False),
                Family("Obturateur de caisse", DIAMETERS, "SMALL", (6, 20), cross=COLOURS, declined=False),
            ),
        ),
    ),
    "CHS": (
        Subsystem(
            "Accessoires de roue",
            (
                Family("Cache-ecrou de roue", COLOURS, "SMALL", (16, 20), cross=("clipse", "visse"),
                       declined=False),
                Family("Antivol de roue", ("cle A", "cle B", "cle C"), "SMALL", (4, 4)),
                Family("Equilibrage adhesif", ("5 g", "10 g", "15 g", "20 g"), "SMALL", (4, 12),
                       cross=FINISHES, declined=False),
            ),
        ),
    ),
    "SAF": (
        Subsystem(
            "Fixation de retenue",
            (
                Family("Vis de ceinture", SIZES_MM, "SMALL", (4, 8), cross=FINISHES, declined=False),
                Family("Rondelle de retenue", SIZES_MM, "SMALL", (4, 12), cross=DIAMETERS, declined=False),
            ),
        ),
    ),
    "HVA": (
        Subsystem(
            "Raccordement",
            (
                Family("Durite de chauffage", ("aller", "retour", "bypass"), "SMALL", (1, 2)),
                Family("Joint torique", DIAMETERS, "SMALL", (4, 12), cross=("EPDM", "HNBR", "silicone"),
                       declined=False),
                Family("Collier de durite", SIZES_MM, "SMALL", (4, 12), cross=FINISHES, declined=False),
            ),
        ),
    ),
}


SUPPLIER_BY_CATEGORY = {
    "Freinage": ("DEL", "VAL"),
    "Chassis": ("VAL", "DEL"),
    "Motorisation": ("VAL", "SUM"),
    "Electrique": ("YZK", "SUM"),
    "Carrosserie": ("DEL", "VAL"),
    "Interieur": ("YZK", "SUM"),
    "Confort": ("VAL", "SUM"),
    "Securite": ("DEL", "SUM"),
}


def generate_bom() -> list[dict]:
    """Build the full nomenclature, deterministically.

    Returns one dict per reference, ordered by system then subsystem, exactly the
    order an engineering BOM is read in.
    """
    rng = random.Random(SEED)
    lines: list[dict] = []
    counters: dict[str, int] = {}

    for system in SYSTEMS:
        declinations = SYSTEM_DECLINATIONS.get(system.code, ())
        subsystems = system.subsystems + CONSUMABLE_SUBSYSTEMS.get(system.code, ())
        for subsystem in subsystems:
            for family in subsystem.families:
                # A family spans its variants, its optional second axis, and the
                # configuration declinations of its system.
                second_axis = family.cross or ("",)
                configs = declinations if (family.declined and declinations) else ("",)

                for variant in family.variants:
                    for cross in second_axis:
                        for config in configs:
                            counters[system.code] = counters.get(system.code, 0) + 1
                            sequence = counters[system.code]
                            reference = f"{system.code}-{sequence:04d}"

                            low, high = family.quantity
                            quantity = low if low == high else rng.randint(low, high)

                            suppliers = SUPPLIER_BY_CATEGORY.get(system.category, ("DEL",))
                            supplier = suppliers[sequence % len(suppliers)]

                            description = " ".join(
                                token for token in (family.name, variant, cross) if token
                            )
                            if config:
                                description = f"{description} - {config}"

                            lines.append(
                                {
                                    "part_reference": reference,
                                    "part_description": description,
                                    "system_code": system.code,
                                    "system_label": system.label,
                                    "subsystem": subsystem.name,
                                    "category": system.category,
                                    "size_class": family.size,
                                    "quantity_per_vehicle": quantity,
                                    "unit": "PCS",
                                    "supplier_code": supplier,
                                }
                            )

    return lines


def bom_statistics(lines: list[dict]) -> dict:
    """Summary used by the seed output and the Excel README sheet."""
    systems: dict[str, int] = {}
    for line in lines:
        systems[line["system_label"]] = systems.get(line["system_label"], 0) + 1
    return {
        "total": len(lines),
        "systems": len(systems),
        "per_system": dict(sorted(systems.items(), key=lambda item: -item[1])),
        "total_pieces_per_vehicle": sum(line["quantity_per_vehicle"] for line in lines),
    }


if __name__ == "__main__":  # pragma: no cover - manual inspection
    generated = generate_bom()
    stats = bom_statistics(generated)
    print(f"{stats['total']} references across {stats['systems']} systems")
    print(f"{stats['total_pieces_per_vehicle']} pieces fitted per vehicle")
    for label, count in stats["per_system"].items():
        print(f"  {label:28} {count:5}")
