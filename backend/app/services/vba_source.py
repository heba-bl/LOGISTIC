"""The VBA behind SLCC_Logistics_Operations.xlsm, kept as reviewable text.

The macros live here rather than inside a binary so they can be read, diffed and
reviewed like the rest of the codebase. `scripts/build_vba_project.py` compiles
them into `app/assets/vbaProject.bin` once, and the workbook generator injects
that artefact into every rebuild.

A word on what the Excel-side checks are worth. The validation codes are stored
as salted SHA-256 digests on a very-hidden, password-protected sheet, and the
maker/checker rule is enforced before a row can be marked approved. That stops
an operator from casually approving their own work. It is *not* a security
boundary: anyone determined enough can read VBA. The boundary is the server -
`import_service` re-runs every one of these checks on the way in, and refuses
what does not pass. Excel is the shop-floor tool; the backend is the authority.
"""

from __future__ import annotations

#: Sheet names, shared with the workbook generator so the two cannot drift.
SHEETS = {
    "home": "ACCUEIL",
    "users": "UTILISATEURS",
    "articles": "ARTICLES",
    "bom": "BOM_VEHICULE",
    "reception": "RECEPTION",
    "inspection": "INSPECTION",
    "quality": "QUALITE",
    "red_cage": "RED_CAGE",
    "warehouse": "WAREHOUSE",
    "movements": "MOUVEMENTS_STOCK",
    "production": "PRODUCTION",
    "issues": "SORTIES",
    "locations": "EMPLACEMENTS",
    "history": "HISTORIQUE",
    "config": "CONFIGURATION",
}

#: Statuses a task moves through. Mirrors `ImportStatus` on the backend.
STATUS_DRAFT = "BROUILLON"
STATUS_PENDING = "EN ATTENTE DE VALIDATION"
STATUS_APPROVED = "VALIDE"
STATUS_REJECTED = "REJETE"
STATUS_SYNCED = "SYNCHRONISE"


# --------------------------------------------------------------------- SHA-256
#: A self-contained SHA-256. VBA has no hashing of its own, and reaching into
#: .NET through COM fails on machines where it is not registered - which is
#: exactly the shop-floor PC this has to run on.
_SHA256 = r'''
Option Explicit

Private K(0 To 63) As Long
Private KReady As Boolean

Private Sub InitK()
    Dim v As Variant, i As Long
    v = Array( _
        "428a2f98", "71374491", "b5c0fbcf", "e9b5dba5", "3956c25b", "59f111f1", "923f82a4", "ab1c5ed5", _
        "d807aa98", "12835b01", "243185be", "550c7dc3", "72be5d74", "80deb1fe", "9bdc06a7", "c19bf174", _
        "e49b69c1", "efbe4786", "0fc19dc6", "240ca1cc", "2de92c6f", "4a7484aa", "5cb0a9dc", "76f988da", _
        "983e5152", "a831c66d", "b00327c8", "bf597fc7", "c6e00bf3", "d5a79147", "06ca6351", "14292967", _
        "27b70a85", "2e1b2138", "4d2c6dfc", "53380d13", "650a7354", "766a0abb", "81c2c92e", "92722c85", _
        "a2bfe8a1", "a81a664b", "c24b8b70", "c76c51a3", "d192e819", "d6990624", "f40e3585", "106aa070", _
        "19a4c116", "1e376c08", "2748774c", "34b0bcb5", "391c0cb3", "4ed8aa4a", "5b9cca4f", "682e6ff3", _
        "748f82ee", "78a5636f", "84c87814", "8cc70208", "90befffa", "a4506ceb", "bef9a3f7", "c67178f2")
    For i = 0 To 63
        K(i) = HexToLong(CStr(v(i)))
    Next i
    KReady = True
End Sub

Private Function HexToLong(ByVal h As String) As Long
    Dim hi As Long, lo As Long
    hi = CLng("&H" & Left$(h, 4))
    lo = CLng("&H" & Right$(h, 4))
    HexToLong = (hi * &H10000) Or lo
    If hi >= &H8000& Then HexToLong = ((hi - &H10000) * &H10000) Or lo
End Function

Private Function RotR(ByVal x As Long, ByVal n As Long) As Long
    RotR = ShiftR(x, n) Or ShiftL(x, 32 - n)
End Function

Private Function ShiftR(ByVal x As Long, ByVal n As Long) As Long
    If n = 0 Then ShiftR = x: Exit Function
    If n > 31 Then ShiftR = 0: Exit Function
    ShiftR = (x And &H7FFFFFFF) \ (2 ^ n)
    If x < 0 Then ShiftR = ShiftR Or (&H40000000 \ (2 ^ (n - 1)))
End Function

Private Function ShiftL(ByVal x As Long, ByVal n As Long) As Long
    Dim i As Long
    If n = 0 Then ShiftL = x: Exit Function
    If n > 31 Then ShiftL = 0: Exit Function
    ShiftL = x
    For i = 1 To n
        If (ShiftL And &H40000000) <> 0 Then
            ShiftL = (ShiftL And &H3FFFFFFF) * 2 Or &H80000000
        Else
            ShiftL = (ShiftL And &H3FFFFFFF) * 2
        End If
    Next i
End Function

Private Function AddL(ByVal a As Long, ByVal b As Long) As Long
    Dim x As Double
    x = (a And &H7FFFFFFF) + (b And &H7FFFFFFF)
    If a < 0 Then x = x + 2147483648#
    If b < 0 Then x = x + 2147483648#
    x = x - Int(x / 4294967296#) * 4294967296#
    If x >= 2147483648# Then
        AddL = CLng(x - 4294967296#)
    Else
        AddL = CLng(x)
    End If
End Function

'' SHA-256 of a string, returned lowercase hex. Used only to compare a typed
'' code with a stored digest - never to protect anything on its own.
Public Function Sha256Hex(ByVal message As String) As String
    Dim H(0 To 7) As Long, w(0 To 63) As Long
    Dim bytes() As Byte, padded() As Byte
    Dim i As Long, j As Long, chunk As Long, total As Long
    Dim a As Long, b As Long, c As Long, d As Long
    Dim e As Long, f As Long, g As Long, hh As Long
    Dim s0 As Long, s1 As Long, ch As Long, maj As Long, t1 As Long, t2 As Long
    Dim bitLen As Double, result As String

    If Not KReady Then InitK

    H(0) = HexToLong("6a09e667"): H(1) = HexToLong("bb67ae85")
    H(2) = HexToLong("3c6ef372"): H(3) = HexToLong("a54ff53a")
    H(4) = HexToLong("510e527f"): H(5) = HexToLong("9b05688c")
    H(6) = HexToLong("1f83d9ab"): H(7) = HexToLong("5be0cd19")

    bytes = StringToBytes(message)
    total = UBound(bytes) - LBound(bytes) + 1
    If total < 0 Then total = 0

    Dim padLen As Long
    padLen = 64 - ((total + 9) Mod 64)
    If padLen = 64 Then padLen = 0
    ReDim padded(0 To total + 8 + padLen)
    For i = 0 To total - 1
        padded(i) = bytes(i)
    Next i
    padded(total) = &H80
    bitLen = total * 8#
    For i = 0 To 7
        padded(UBound(padded) - i) = CByte(Int(bitLen / (2 ^ (8 * i))) And &HFF)
    Next i

    For chunk = 0 To (UBound(padded) + 1) \ 64 - 1
        For i = 0 To 15
            j = chunk * 64 + i * 4
            w(i) = (CLng(padded(j)) * &H1000000) Or (CLng(padded(j + 1)) * &H10000) _
                   Or (CLng(padded(j + 2)) * &H100&) Or CLng(padded(j + 3))
            If padded(j) >= &H80 Then
                w(i) = ((CLng(padded(j)) - 256) * &H1000000) Or (CLng(padded(j + 1)) * &H10000) _
                       Or (CLng(padded(j + 2)) * &H100&) Or CLng(padded(j + 3))
            End If
        Next i
        For i = 16 To 63
            s0 = RotR(w(i - 15), 7) Xor RotR(w(i - 15), 18) Xor ShiftR(w(i - 15), 3)
            s1 = RotR(w(i - 2), 17) Xor RotR(w(i - 2), 19) Xor ShiftR(w(i - 2), 10)
            w(i) = AddL(AddL(AddL(w(i - 16), s0), w(i - 7)), s1)
        Next i

        a = H(0): b = H(1): c = H(2): d = H(3)
        e = H(4): f = H(5): g = H(6): hh = H(7)

        For i = 0 To 63
            s1 = RotR(e, 6) Xor RotR(e, 11) Xor RotR(e, 25)
            ch = (e And f) Xor ((Not e) And g)
            t1 = AddL(AddL(AddL(AddL(hh, s1), ch), K(i)), w(i))
            s0 = RotR(a, 2) Xor RotR(a, 13) Xor RotR(a, 22)
            maj = (a And b) Xor (a And c) Xor (b And c)
            t2 = AddL(s0, maj)
            hh = g: g = f: f = e: e = AddL(d, t1)
            d = c: c = b: b = a: a = AddL(t1, t2)
        Next i

        H(0) = AddL(H(0), a): H(1) = AddL(H(1), b)
        H(2) = AddL(H(2), c): H(3) = AddL(H(3), d)
        H(4) = AddL(H(4), e): H(5) = AddL(H(5), f)
        H(6) = AddL(H(6), g): H(7) = AddL(H(7), hh)
    Next chunk

    For i = 0 To 7
        result = result & LongToHex(H(i))
    Next i
    Sha256Hex = LCase$(result)
End Function

Private Function LongToHex(ByVal v As Long) As String
    Dim hi As Long, lo As Long
    lo = v And &HFFFF&
    hi = ShiftR(v, 16) And &HFFFF&
    LongToHex = Right$("0000" & Hex$(hi), 4) & Right$("0000" & Hex$(lo), 4)
End Function

'' UTF-8 bytes of a string: the digest must match what Python computes.
Private Function StringToBytes(ByVal s As String) As Byte()
    Dim out() As Byte, n As Long, i As Long, code As Long
    ReDim out(0 To Len(s) * 4)
    n = 0
    For i = 1 To Len(s)
        code = AscW(Mid$(s, i, 1))
        If code < 0 Then code = code + 65536
        If code < &H80 Then
            out(n) = CByte(code): n = n + 1
        ElseIf code < &H800 Then
            out(n) = CByte(&HC0 Or (code \ &H40)): n = n + 1
            out(n) = CByte(&H80 Or (code And &H3F)): n = n + 1
        Else
            out(n) = CByte(&HE0 Or (code \ &H1000)): n = n + 1
            out(n) = CByte(&H80 Or ((code \ &H40) And &H3F)): n = n + 1
            out(n) = CByte(&H80 Or (code And &H3F)): n = n + 1
        End If
    Next i
    If n = 0 Then
        ReDim out(0 To 0)
        Dim empty() As Byte
        empty = out
        StringToBytes = empty
        Exit Function
    End If
    ReDim Preserve out(0 To n - 1)
    StringToBytes = out
End Function
'''


# ------------------------------------------------------------------- workflow
_WORKFLOW = r'''
Option Explicit

'' Sheet names, kept in one place so a rename breaks in one spot only.
Public Const SH_USERS As String = "UTILISATEURS"
Public Const SH_HISTORY As String = "HISTORIQUE"
Public Const SH_CONFIG As String = "CONFIGURATION"
Public Const SH_HOME As String = "ACCUEIL"

Public Const ST_DRAFT As String = "BROUILLON"
Public Const ST_PENDING As String = "EN ATTENTE DE VALIDATION"
Public Const ST_APPROVED As String = "VALIDE"
Public Const ST_REJECTED As String = "REJETE"

'' Every operational sheet uses the same trailing block, so one set of routines
'' drives Reception, Inspection, Quality, Warehouse and Production alike.
Public Const COL_MAKER As String = "MATRICULE_OPERATEUR"
Public Const COL_STATUS As String = "STATUT"
Public Const COL_CHECKER As String = "MATRICULE_CHECKER"
Public Const COL_SUBMITTED As String = "DATE_SOUMISSION"
Public Const COL_VALIDATED As String = "DATE_VALIDATION"
Public Const COL_REASON As String = "MOTIF_REJET"
Public Const COL_SYNC_ID As String = "ID_SYNC"
Public Const COL_SYNC_STATUS As String = "ETAT_SYNC"
Public Const COL_TOKEN As String = "JETON_VALIDATION"

'' Read by all three modules, so Public: a Private constant here stops the
'' others compiling, and VBA only says so when their code is first run.
Public Const HEADER_ROW As Long = 4

'' Row 3 of every entry sheet carries the synchronisation banner.
Public Const FRESH_ROW As Long = 3

'' ---------------------------------------------------------------- utilities
Public Function SheetByName(ByVal sheetName As String) As Worksheet
    Dim book As Workbook, found As Worksheet

    On Error Resume Next
    '' The file the operator is working in, which is the one the ribbon acts on.
    ''
    '' Deliberately never the project's own workbook object. This project is
    '' assembled outside Excel and injected into the generated file, so its
    '' document modules were built for a different workbook: touching that object
    '' raises error 429, because VBA cannot bind the class to a real document.
    '' Every lookup here goes through the sheet the operator is on, then through
    '' the open workbooks.
    Set found = ActiveSheet.Parent.Worksheets(sheetName)
    If found Is Nothing Then
        For Each book In Application.Workbooks
            Set found = book.Worksheets(sheetName)
            If Not found Is Nothing Then Exit For
        Next book
    End If
    On Error GoTo 0

    Set SheetByName = found
End Function


'' Re-protect a sheet the way the workbook was built.
''
'' One place for the convention, so a macro that unprotects to write cannot put
'' the sheet back differently from the way it was found.
'' Turn the live DATE and HEURE formulas into fixed text.
''
'' They are formulas so the operator never types a date; but TODAY() and NOW()
'' re-evaluate every time the file opens, and a record whose date moves is not a
'' record. Submitting is the moment it stops being a draft, so that is where the
'' stamp is fixed.
Public Sub FreezeStamp(ByVal ws As Worksheet, ByVal r As Long)
    '' `stamps`, not `names`: Names is Excel's own, and assigning to it here
    '' raises error 450 instead of filling an array.
    Dim stamps As Variant, i As Long, c As Long
    stamps = Array("DATE", "HEURE")
    For i = LBound(stamps) To UBound(stamps)
        c = ColumnIndex(ws, CStr(stamps(i)))
        If c > 0 Then ws.Cells(r, c).Value = ws.Cells(r, c).Text
    Next i
End Sub

Public Sub ProtectSheet(ByVal ws As Worksheet)
    '' Every cell stays reachable on purpose - a checker has to put the cursor on
    '' a submitted, and therefore locked, line to validate it. That is Excel's
    '' default, so it is left alone rather than re-asserted: assigning
    '' EnableSelection to a sheet already protected is its own source of errors.
    ws.Protect UserInterfaceOnly:=True
End Sub

'' How many columns the header row actually declares.
''
'' Deliberately not End(xlToLeft): that skips hidden columns, and the technical
'' columns are folded away on purpose. A short scan that tolerates a gap finds
'' them all, visible or not.
Public Function LastHeaderColumn(ws As Worksheet) As Long
    Dim c As Long, blanks As Long
    For c = 1 To 200
        If Len(Trim$(CStr(ws.Cells(HEADER_ROW, c).Value))) = 0 Then
            blanks = blanks + 1
            If blanks >= 5 Then Exit For
        Else
            blanks = 0
            LastHeaderColumn = c
        End If
    Next c
End Function

Public Function ColumnIndex(ws As Worksheet, ByVal header As String) As Long
    Dim c As Long, last As Long
    last = LastHeaderColumn(ws)
    For c = 1 To last
        If UCase$(Trim$(CStr(ws.Cells(HEADER_ROW, c).Value))) = UCase$(header) Then
            ColumnIndex = c
            Exit Function
        End If
    Next c
    ColumnIndex = 0
End Function

Public Function LastDataRow(ws As Worksheet) As Long
    Dim r As Long
    r = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    If r < HEADER_ROW Then r = HEADER_ROW
    LastDataRow = r
End Function

'' Is this sheet one an operator fills in? Only those carry a STATUT column.
Public Function IsOperationalSheet(ws As Worksheet) As Boolean
    IsOperationalSheet = (ColumnIndex(ws, COL_STATUS) > 0)
End Function

'' ------------------------------------------------------------------- people
'' Look a matricule up in UTILISATEURS. Returns the row, or 0 when unknown.
Public Function FindUser(ByVal matricule As String) As Long
    Dim ws As Worksheet, r As Long, last As Long
    Set ws = SheetByName(SH_USERS)
    If ws Is Nothing Then Exit Function
    last = LastDataRow(ws)
    For r = HEADER_ROW + 1 To last
        If UCase$(Trim$(CStr(ws.Cells(r, 1).Value))) = UCase$(Trim$(matricule)) Then
            FindUser = r
            Exit Function
        End If
    Next r
End Function

Public Function UserField(ByVal matricule As String, ByVal header As String) As String
    Dim ws As Worksheet, r As Long, c As Long
    Set ws = SheetByName(SH_USERS)
    r = FindUser(matricule)
    If r = 0 Then Exit Function
    c = ColumnIndex(ws, header)
    If c = 0 Then Exit Function
    UserField = Trim$(CStr(ws.Cells(r, c).Value))
End Function

Public Function UserIsActive(ByVal matricule As String) As Boolean
    UserIsActive = (UCase$(UserField(matricule, "STATUT")) = "ACTIF")
End Function

'' ------------------------------------------------------------------ history
Public Sub WriteHistory(ByVal recordId As String, ByVal action As String, _
                        ByVal maker As String, ByVal checker As String, _
                        ByVal statusBefore As String, ByVal statusAfter As String, _
                        ByVal reason As String, ByVal sourceSheet As String)
    Dim ws As Worksheet, r As Long
    Set ws = SheetByName(SH_HISTORY)
    If ws Is Nothing Then Exit Sub
    ws.Unprotect
    r = LastDataRow(ws) + 1
    ws.Cells(r, 1).Value = recordId
    ws.Cells(r, 2).Value = action
    ws.Cells(r, 3).Value = maker
    ws.Cells(r, 4).Value = checker
    ws.Cells(r, 5).Value = Format$(Now, "dd/mm/yyyy")
    ws.Cells(r, 6).Value = Format$(Now, "hh:nn:ss")
    ws.Cells(r, 7).Value = statusBefore
    ws.Cells(r, 8).Value = statusAfter
    ws.Cells(r, 9).Value = reason
    ws.Cells(r, 10).Value = sourceSheet
    ws.Cells(r, 11).Value = Environ$("USERNAME")
    ProtectSheet ws
End Sub

'' --------------------------------------------------------- maker: submitting
'' The operator declares a line finished. Everything below is checked before
'' the status moves - a half-filled row must not reach a manager's queue.
'' The ribbon calls these with the control that was clicked, so each one has to
'' accept an argument it does not use. Declared Optional so they can still be run
'' by name - from the macro list, or from a test - with nothing passed.
Public Sub TerminerMaTache(Optional control As Object)
    Dim ws As Worksheet, r As Long
    Dim colStatus As Long, colMaker As Long, colSubmitted As Long, colSync As Long
    Dim maker As String, currentStatus As String, recordId As String
    Dim missing As String

    Set ws = ActiveSheet
    If Not IsOperationalSheet(ws) Then
        MsgBox "Cette feuille n'est pas une feuille de saisie.", vbExclamation, "SLCC"
        Exit Sub
    End If

    r = ActiveCell.Row
    If r <= HEADER_ROW Then
        MsgBox "Selectionnez la ligne a soumettre.", vbExclamation, "SLCC"
        Exit Sub
    End If

    colStatus = ColumnIndex(ws, COL_STATUS)
    colMaker = ColumnIndex(ws, COL_MAKER)
    colSubmitted = ColumnIndex(ws, COL_SUBMITTED)
    colSync = ColumnIndex(ws, COL_SYNC_ID)

    currentStatus = UCase$(Trim$(CStr(ws.Cells(r, colStatus).Value)))
    If currentStatus = ST_PENDING Then
        MsgBox "Cette ligne est deja en attente de validation.", vbInformation, "SLCC"
        Exit Sub
    End If
    If currentStatus = ST_APPROVED Then
        MsgBox "Cette ligne est validee: elle ne peut plus etre modifiee.", vbExclamation, "SLCC"
        Exit Sub
    End If

    maker = Trim$(CStr(ws.Cells(r, colMaker).Value))
    If Len(maker) = 0 Then
        MsgBox "Saisissez votre matricule avant de terminer la tache.", vbExclamation, "SLCC"
        Exit Sub
    End If
    If FindUser(maker) = 0 Then
        MsgBox "Matricule inconnu: " & maker, vbCritical, "SLCC"
        Exit Sub
    End If
    If Not UserIsActive(maker) Then
        MsgBox "Ce matricule est inactif: " & maker, vbCritical, "SLCC"
        Exit Sub
    End If

    missing = MissingFields(ws, r)
    If Len(missing) > 0 Then
        MsgBox "Champs obligatoires manquants:" & vbCrLf & missing, vbExclamation, "SLCC"
        Exit Sub
    End If

    recordId = CStr(ws.Cells(r, 1).Value)

    ws.Unprotect
    If Len(recordId) = 0 Then
        recordId = NextRecordId(ws)
        ws.Cells(r, 1).Value = recordId
    End If
    FreezeStamp ws, r
    ws.Cells(r, colStatus).Value = ST_PENDING
    If colSubmitted > 0 Then
        ws.Cells(r, colSubmitted).Value = Format$(Now, "dd/mm/yyyy hh:nn")
    End If
    If colSync > 0 And Len(Trim$(CStr(ws.Cells(r, colSync).Value))) = 0 Then
        ws.Cells(r, colSync).Value = BuildSyncId(ws.Name, recordId)
    End If
    LockRow ws, r
    ProtectSheet ws

    WriteHistory recordId, "SUBMIT", maker, "", ST_DRAFT, ST_PENDING, "", ws.Name
    MsgBox "Tache soumise." & vbCrLf & _
           "Statut: " & ST_PENDING & vbCrLf & _
           "Un responsable de la zone doit maintenant valider.", vbInformation, "SLCC"
End Sub

'' Required columns are marked in the header with a bold font by the generator;
'' this reads that same convention rather than duplicating a list.
Private Function MissingFields(ws As Worksheet, ByVal r As Long) As String
    Dim c As Long, last As Long, out As String, header As String
    last = LastHeaderColumn(ws)
    For c = 2 To last
        header = UCase$(Trim$(CStr(ws.Cells(HEADER_ROW, c).Value)))
        If ws.Cells(HEADER_ROW, c).Font.Bold And header <> COL_STATUS Then
            If Len(Trim$(CStr(ws.Cells(r, c).Value))) = 0 Then
                out = out & " - " & ws.Cells(HEADER_ROW, c).Value & vbCrLf
            End If
        End If
    Next c
    MissingFields = out
End Function

Private Function NextRecordId(ws As Worksheet) As String
    Dim prefix As String, r As Long, last As Long, n As Long, v As String
    prefix = Left$(ws.Name, 3) & "-"
    last = LastDataRow(ws)
    For r = HEADER_ROW + 1 To last
        v = CStr(ws.Cells(r, 1).Value)
        If InStr(v, "-") > 0 Then
            If IsNumeric(Mid$(v, InStr(v, "-") + 1)) Then
                If CLng(Mid$(v, InStr(v, "-") + 1)) > n Then n = CLng(Mid$(v, InStr(v, "-") + 1))
            End If
        End If
    Next r
    NextRecordId = prefix & Format$(n + 1, "0000")
End Function

'' A stable id so the backend can reject a line it has already taken in.
Public Function BuildSyncId(ByVal sheetName As String, ByVal recordId As String) As String
    BuildSyncId = "SLCC-" & Left$(sheetName, 3) & "-" & Replace(recordId, "-", "") & _
                  "-" & Format$(Now, "yyyymmddhhnnss")
End Function

Private Sub LockRow(ws As Worksheet, ByVal r As Long)
    Dim last As Long
    last = LastHeaderColumn(ws)
    ws.Range(ws.Cells(r, 1), ws.Cells(r, last)).Locked = True
End Sub

Private Sub UnlockRow(ws As Worksheet, ByVal r As Long)
    Dim last As Long
    last = LastHeaderColumn(ws)
    ws.Range(ws.Cells(r, 1), ws.Cells(r, last)).Locked = False
End Sub

'' ------------------------------------------------------ checker: validating
Public Sub Valider(Optional control As Object)
    DecideRow True
End Sub

Public Sub Rejeter(Optional control As Object)
    DecideRow False
End Sub

'' One routine for both decisions: they check exactly the same things, and
'' splitting them would be two places to forget the maker/checker rule.
Private Sub DecideRow(ByVal approve As Boolean)
    Dim ws As Worksheet
    Dim colStatus As Long, colMaker As Long, colChecker As Long
    Dim colValidated As Long, colReason As Long, colSync As Long, colToken As Long
    Dim checker As String, code As String, reason As String, zone As String
    Dim rows() As Long, pending As Long, r As Long, i As Long
    Dim maker As String, recordId As String
    Dim syncId As String, token As String, refusal As String
    Dim done As Long, failed As Long, selfCheck As Long
    Dim summary As String, detail As String

    Set ws = ActiveSheet
    If Not IsOperationalSheet(ws) Then
        MsgBox "Cette feuille n'est pas une feuille de saisie.", vbExclamation, "SLCC"
        Exit Sub
    End If

    colStatus = ColumnIndex(ws, COL_STATUS)
    colMaker = ColumnIndex(ws, COL_MAKER)
    colChecker = ColumnIndex(ws, COL_CHECKER)
    colValidated = ColumnIndex(ws, COL_VALIDATED)
    colReason = ColumnIndex(ws, COL_REASON)
    colSync = ColumnIndex(ws, COL_SYNC_ID)
    colToken = ColumnIndex(ws, COL_TOKEN)

    '' Every pending row the selection touches. One cell selected means one row,
    '' so the single-line habit keeps working unchanged.
    pending = CollectPending(ws, colStatus, rows)
    If pending = 0 Then
        MsgBox "Aucune ligne '" & ST_PENDING & "' dans la selection.", vbExclamation, "SLCC"
        Exit Sub
    End If

    checker = Trim$(InputBox("VALIDATION RESPONSABLE" & vbCrLf & vbCrLf & _
                             pending & " ligne(s) selectionnee(s)." & vbCrLf & _
                             "Matricule responsable :", "SLCC"))
    If Len(checker) = 0 Then Exit Sub

    If FindUser(checker) = 0 Then
        MsgBox "VALIDATION REFUSEE" & vbCrLf & "Matricule inconnu.", vbCritical, "SLCC"
        Exit Sub
    End If
    If Not UserIsActive(checker) Then
        MsgBox "VALIDATION REFUSEE" & vbCrLf & "Compte inactif.", vbCritical, "SLCC"
        Exit Sub
    End If
    If UCase$(UserField(checker, "DROIT_VALIDATION")) <> "OUI" Then
        MsgBox "VALIDATION REFUSEE" & vbCrLf & _
               "Ce matricule n'a pas le droit de validation.", vbCritical, "SLCC"
        Exit Sub
    End If

    zone = NormalizeZone(UserField(checker, "ZONE"))
    If zone <> NormalizeZone(ZoneOfSheet(ws.Name)) And zone <> "LOGISTIQUE" Then
        MsgBox "VALIDATION REFUSEE" & vbCrLf & _
               "Ce responsable depend de la zone " & zone & "," & vbCrLf & _
               "pas de " & ZoneOfSheet(ws.Name) & ".", vbCritical, "SLCC"
        Exit Sub
    End If

    '' What is about to be signed, before the code is asked for.
    detail = SelectionSummary(ws, rows, pending, colMaker, checker, selfCheck)
    If selfCheck = pending Then
        MsgBox "VALIDATION REFUSEE" & vbCrLf & vbCrLf & _
               "Vous ne pouvez pas valider votre propre saisie." & vbCrLf & _
               "Un responsable different doit intervenir.", vbCritical, "SLCC"
        Exit Sub
    End If

    If MsgBox(IIf(approve, "VALIDER", "REJETER") & " " & (pending - selfCheck) & _
              " ligne(s) ?" & vbCrLf & vbCrLf & detail & vbCrLf & _
              "Votre matricule sera enregistre sur chacune.", _
              vbQuestion + vbOKCancel, "SLCC") <> vbOK Then Exit Sub

    If Not approve Then
        reason = Trim$(InputBox("Motif du rejet (obligatoire) :", "SLCC"))
        If Len(reason) = 0 Then
            MsgBox "Un rejet exige un motif.", vbExclamation, "SLCC"
            Exit Sub
        End If
    End If

    code = Trim$(InputBox("Code de validation :", "SLCC"))
    If Len(code) = 0 Then Exit Sub

    Application.ScreenUpdating = False
    For i = 1 To pending
        r = rows(i)
        maker = Trim$(CStr(ws.Cells(r, colMaker).Value))
        recordId = CStr(ws.Cells(r, 1).Value)

        '' The rule the whole workflow exists for, checked line by line: a bulk
        '' selection must not become a way to slip your own entry through.
        If UCase$(checker) = UCase$(maker) Then
            WriteHistory recordId, "REFUS_AUTO_VALIDATION", maker, checker, _
                         ST_PENDING, ST_PENDING, "maker = checker", ws.Name
            GoTo NextRow
        End If

        syncId = Trim$(CStr(ws.Cells(r, colSync).Value))
        If Len(syncId) = 0 Then
            syncId = BuildSyncId(ws.Name, recordId)
            ws.Unprotect
            ws.Cells(r, colSync).Value = syncId
            ProtectSheet ws
        End If

        '' One signature per line. The server never signs a batch, so the audit
        '' still holds N separate decisions rather than one blanket approval.
        token = RequestValidationToken(ws.Name, syncId, maker, checker, code, refusal)
        If Len(token) = 0 Then
            failed = failed + 1
            WriteHistory recordId, "VALIDATION_REFUSEE", maker, checker, _
                         ST_PENDING, ST_PENDING, refusal, ws.Name
            GoTo NextRow
        End If

        ws.Unprotect
        If approve Then
            ws.Cells(r, colStatus).Value = ST_APPROVED
            ws.Cells(r, colChecker).Value = checker
            If colToken > 0 Then ws.Cells(r, colToken).Value = token
            If colValidated > 0 Then _
                ws.Cells(r, colValidated).Value = Format$(Now, "dd/mm/yyyy hh:nn")
            LockRow ws, r
            WriteHistory recordId, "APPROVE", maker, checker, ST_PENDING, ST_APPROVED, "", ws.Name
        Else
            ws.Cells(r, colStatus).Value = ST_REJECTED
            ws.Cells(r, colChecker).Value = checker
            If colReason > 0 Then ws.Cells(r, colReason).Value = reason
            '' A rejected line goes back to the operator, so it must be editable.
            UnlockRow ws, r
            WriteHistory recordId, "REJECT", maker, checker, ST_PENDING, ST_REJECTED, reason, ws.Name
        End If
        ProtectSheet ws
        done = done + 1
NextRow:
    Next i
    Application.ScreenUpdating = True

    summary = IIf(approve, "VALIDE", "REJETE") & vbCrLf & vbCrLf & _
              done & " ligne(s) traitee(s) par " & checker & "."
    If selfCheck > 0 Then _
        summary = summary & vbCrLf & selfCheck & " ignoree(s): saisie par vous-meme."
    If failed > 0 Then _
        summary = summary & vbCrLf & failed & " refusee(s) par SLCC."
    MsgBox summary, vbInformation, "SLCC"
End Sub

'' Pending rows inside the current selection, in sheet order.
''
'' Returns how many were found and fills `found`. One selected cell yields one
'' row, so validating a single line still works exactly as it did.
Private Function CollectPending(ByVal ws As Worksheet, ByVal colStatus As Long, _
                                ByRef found() As Long) As Long
    Dim area As Range, cell As Range
    Dim r As Long, last As Long, total As Long
    Dim seen As Object

    last = LastDataRow(ws)
    ReDim found(1 To Application.Max(last, 1))
    Set seen = Nothing

    For Each area In Selection.Areas
        For r = area.Row To area.Row + area.Rows.Count - 1
            If r > HEADER_ROW And r <= last Then
                If UCase$(Trim$(CStr(ws.Cells(r, colStatus).Value))) = ST_PENDING Then
                    If Not AlreadyCollected(found, total, r) Then
                        total = total + 1
                        found(total) = r
                    End If
                End If
            End If
        Next r
    Next area

    CollectPending = total
End Function

Private Function AlreadyCollected(ByRef found() As Long, ByVal total As Long, _
                                  ByVal r As Long) As Boolean
    Dim i As Long
    For i = 1 To total
        If found(i) = r Then
            AlreadyCollected = True
            Exit Function
        End If
    Next i
End Function

'' A readable digest of what the responsible is about to sign.
''
'' Counts, not a list of thirty identifiers: the point is to notice a surprise -
'' a line you entered yourself, a quantity gap - not to re-read the sheet.
Private Function SelectionSummary(ByVal ws As Worksheet, ByRef rows() As Long, _
                                  ByVal pending As Long, ByVal colMaker As Long, _
                                  ByVal checker As String, ByRef selfCheck As Long) As String
    Dim i As Long, r As Long
    Dim makers As String, refs As Object, gaps As Long
    Dim colRef As Long, colGap As Long, reference As String
    Dim distinct As Long

    colRef = ColumnIndex(ws, "REFERENCE_PIECE")
    colGap = ColumnIndex(ws, "ECART")
    selfCheck = 0
    distinct = 0

    For i = 1 To pending
        r = rows(i)
        If UCase$(Trim$(CStr(ws.Cells(r, colMaker).Value))) = UCase$(checker) Then
            selfCheck = selfCheck + 1
        End If
        If colRef > 0 Then
            reference = Trim$(CStr(ws.Cells(r, colRef).Value))
            If Len(reference) > 0 And InStr(makers, "|" & reference & "|") = 0 Then
                makers = makers & "|" & reference & "|"
                distinct = distinct + 1
            End If
        End If
        If colGap > 0 Then
            If Val(CStr(ws.Cells(r, colGap).Value)) <> 0 Then gaps = gaps + 1
        End If
    Next i

    SelectionSummary = pending & " ligne(s)"
    If distinct > 0 Then SelectionSummary = SelectionSummary & ", " & distinct & " reference(s)"
    If gaps > 0 Then SelectionSummary = SelectionSummary & ", " & gaps & " avec ecart"
    SelectionSummary = SelectionSummary & "."
    If selfCheck > 0 Then
        SelectionSummary = SelectionSummary & vbCrLf & _
                           selfCheck & " ligne(s) saisie(s) par vous seront ignoree(s)."
    End If
End Function

'' Which zone owns a sheet. Drives the "right manager for the right sheet" rule.
'' Reduce a zone to one spelling, whichever side it came from.
''
'' The database names its zones in English - Zone.QUALITY, Zone.LOGISTICS -
'' and those words are written straight into the UTILISATEURS sheet. The sheet
'' names and this module are in French. Comparing the two raw strings meant
'' QUALITY <> QUALITE and LOGISTICS <> LOGISTIQUE, so five of the nine
'' responsibles could not validate anything at all - silently, with a message
'' telling them they belonged to another zone.
''
'' Normalising both sides is what stops that returning: a rename on either
'' side now has to pass through here, and here is one place.
Public Function NormalizeZone(ByVal zone As String) As String
    Select Case UCase$(Trim$(zone))
        Case "QUALITY", "QUALITE": NormalizeZone = "QUALITE"
        Case "LOGISTICS", "LOGISTIQUE": NormalizeZone = "LOGISTIQUE"
        Case "RECEIVING", "RECEPTION": NormalizeZone = "RECEPTION"
        Case "WAREHOUSE", "ENTREPOT": NormalizeZone = "WAREHOUSE"
        Case "PRODUCTION": NormalizeZone = "PRODUCTION"
        Case "INSPECTION": NormalizeZone = "QUALITE"
        Case Else: NormalizeZone = UCase$(Trim$(zone))
    End Select
End Function

Public Function ZoneOfSheet(ByVal sheetName As String) As String
    Select Case UCase$(sheetName)
        Case "RECEPTION": ZoneOfSheet = "RECEPTION"
        '' An inspector never signs off their own trade, so the inspection
        '' sheet is validated by quality - as it is on a shop floor.
        Case "INSPECTION": ZoneOfSheet = "QUALITE"
        Case "QUALITE", "RED_CAGE": ZoneOfSheet = "QUALITE"
        '' SORTIES belongs to the warehouse, not to production: the magasin is
        '' what serves the request, so the magasin chief signs it. The server
        '' has always said so - having it here as PRODUCTION meant a production
        '' manager passed this check and was then refused by the API, which is
        '' the worst place to disagree.
        Case "WAREHOUSE", "SORTIES", "MOUVEMENTS_STOCK", "EMPLACEMENTS": ZoneOfSheet = "WAREHOUSE"
        Case "PRODUCTION": ZoneOfSheet = "PRODUCTION"
        Case Else: ZoneOfSheet = "LOGISTIQUE"
    End Select
End Function

'' The typed code is hashed and compared with the stored digest. The plain code
'' is never written anywhere in the workbook.
Public Function CodeIsValid(ByVal matricule As String, ByVal code As String) As Boolean
    Dim ws As Worksheet, r As Long, last As Long, salt As String, expected As String

    Set ws = SheetByName(SH_CONFIG)
    If ws Is Nothing Then Exit Function
    salt = CStr(ws.Range("B2").Value)

    last = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    For r = 5 To last
        If UCase$(Trim$(CStr(ws.Cells(r, 1).Value))) = UCase$(Trim$(matricule)) Then
            expected = LCase$(Trim$(CStr(ws.Cells(r, 2).Value)))
            CodeIsValid = (Sha256Hex(UCase$(Trim$(matricule)) & ":" & Trim$(code) & ":" & salt) = expected)
            Exit Function
        End If
    Next r
End Function

'' ------------------------------------------------------------------- resubmit
'' After a rejection the operator corrects the line and submits it again; the
'' history keeps both attempts.
Public Sub CorrigerEtResoumettre(Optional control As Object)
    Dim ws As Worksheet, r As Long, colStatus As Long
    Set ws = ActiveSheet
    r = ActiveCell.Row
    colStatus = ColumnIndex(ws, COL_STATUS)
    If colStatus = 0 Or r <= HEADER_ROW Then Exit Sub
    If UCase$(Trim$(CStr(ws.Cells(r, colStatus).Value))) <> ST_REJECTED Then
        MsgBox "Seule une ligne rejetee peut etre corrigee.", vbExclamation, "SLCC"
        Exit Sub
    End If
    ws.Unprotect
    ws.Cells(r, colStatus).Value = ST_DRAFT
    UnlockRow ws, r
    ProtectSheet ws
    MsgBox "Ligne rouverte en " & ST_DRAFT & "." & vbCrLf & _
           "Corrigez puis relancez 'Terminer ma tache'.", vbInformation, "SLCC"
End Sub
'''


# ---------------------------------------------------------------------- sync
_SYNC = r'''
Option Explicit

'' Minutes between two unattended pushes.
Private Const AUTO_MINUTES As Double = 5

'' The pending tick, so it can be cancelled. An OnTime still scheduled when the
'' file closes makes Excel reopen it on its own - a timer nobody asked for.
''
'' These belong here and nowhere else: VBA only treats a Private as module state
'' when it stands before the first procedure. Placed further down it is accepted
'' silently and every use of the name fails to compile.
Private gTick As Double
Private gTarget As String
Private gBusy As Boolean

'' Where SLCC listens. Kept on the CONFIGURATION sheet so a site can point the
'' workbook at its own server without touching the code.
Private Function ApiBase() As String
    Dim ws As Worksheet
    Set ws = SheetByName("CONFIGURATION")
    If ws Is Nothing Then
        ApiBase = "http://127.0.0.1:8001/api"
    Else
        ApiBase = CStr(ws.Range("B3").Value)
    End If
End Function

'' Which rows a sheet still owes SLCC.
''
'' Returns how many, fills `batch` with their row numbers and `lines` with their
'' JSON. The batch matters: stamping every approved row instead - which is what
'' this used to do - told the operator that lines nobody sent had been sent, and
'' on a failure it erased the SYNCHRONISE state of rows that had gone through.
Private Function PendingRows(ws As Worksheet, ByRef batch() As Long, _
                             ByRef lines As String, ByRef ignored As Long) As Long
    Dim r As Long, last As Long, total As Long
    Dim colStatus As Long, colSyncState As Long

    colStatus = ColumnIndex(ws, COL_STATUS)
    colSyncState = ColumnIndex(ws, COL_SYNC_STATUS)
    last = LastDataRow(ws)
    ReDim batch(1 To Application.Max(last, 1))
    lines = ""

    For r = HEADER_ROW + 1 To last
        If UCase$(Trim$(CStr(ws.Cells(r, colStatus).Value))) = ST_APPROVED Then
            If colSyncState = 0 Or _
               UCase$(Trim$(CStr(ws.Cells(r, colSyncState).Value))) <> "SYNCHRONISE" Then
                If Len(lines) > 0 Then lines = lines & ","
                lines = lines & RowToJson(ws, r)
                total = total + 1
                batch(total) = r
            End If
        ElseIf Len(Trim$(CStr(ws.Cells(r, 1).Value))) > 0 Then
            ignored = ignored + 1
        End If
    Next r

    PendingRows = total
End Function

'' Send one sheet's validated lines. Never shows anything.
''
'' The ribbon button and the background timer both come through here, so the
'' rule about what may leave the file lives in one place. Only VALIDE lines go:
'' a draft or a pending line is work in progress, and the backend would refuse
'' it anyway - the filter is here so the operator gets a count, not a wall of
'' rejections.
Private Function PushSheet(ws As Worksheet, ByRef sent As Long, _
                           ByRef ignored As Long, ByRef note As String) As Boolean
    Dim batch() As Long, lines As String, payload As String
    Dim response As String, failure As String, httpStatus As Long
    Dim colSyncState As Long

    note = ""
    sent = PendingRows(ws, batch, lines, ignored)
    If sent = 0 Then
        PushSheet = True
        Exit Function
    End If

    colSyncState = ColumnIndex(ws, COL_SYNC_STATUS)

    '' ws.Parent, and not the project's own workbook object: see SheetByName. The
    '' workbook that owns the sheet being synchronised is also the one whose name
    '' belongs in the payload.
    payload = "{""sheet"":""" & ws.Name & """,""file"":""" & ws.Parent.Name & _
              """,""rows"":[" & lines & "]}"

    If Not SlccRequest("POST", ApiBase() & "/excel/sync", payload, _
                       httpStatus, response, failure) Then
        note = failure
        MarkBatch ws, colSyncState, batch, sent, "HORS LIGNE"
        Exit Function
    End If

    If httpStatus < 200 Or httpStatus >= 300 Then
        note = "Reponse " & httpStatus & " - " & Left$(response, 200)
        MarkBatch ws, colSyncState, batch, sent, "ERREUR"
        Exit Function
    End If

    MarkBatch ws, colSyncState, batch, sent, "SYNCHRONISE"
    note = Left$(response, 300)
    PushSheet = True
End Function

Private Sub MarkBatch(ws As Worksheet, ByVal col As Long, ByRef batch() As Long, _
                      ByVal total As Long, ByVal state As String)
    Dim i As Long
    If col = 0 Or total = 0 Then Exit Sub
    ws.Unprotect
    For i = 1 To total
        ws.Cells(batch(i), col).Value = state
    Next i
    ProtectSheet ws
End Sub

'' Push the current sheet, and say what happened.
Public Sub EnregistrerEtSynchroniser(Optional control As Object)
    Dim ws As Worksheet
    Dim sent As Long, ignored As Long, note As String
    Dim ok As Boolean

    Set ws = ActiveSheet
    If Not IsOperationalSheet(ws) Then
        MsgBox "Placez-vous sur une feuille de saisie.", vbExclamation, "SLCC"
        Exit Sub
    End If

    ok = PushSheet(ws, sent, ignored, note)
    StampFreshness ws, ok, sent

    If ok And sent = 0 Then
        MsgBox "Aucune ligne validee a synchroniser." & vbCrLf & _
               ignored & " ligne(s) non validee(s) ignoree(s).", vbInformation, "SLCC"
    ElseIf ok Then
        MsgBox "/ Synchronise" & vbCrLf & vbCrLf & _
               sent & " ligne(s) validee(s) envoyee(s)." & vbCrLf & _
               ignored & " ligne(s) non validee(s) ignoree(s)." & vbCrLf & vbCrLf & _
               note, vbInformation, "SLCC"
    Else
        MsgBox "X SLCC injoignable" & vbCrLf & vbCrLf & _
               "Le fichier reste utilisable: les " & sent & " ligne(s) validee(s)" & vbCrLf & _
               "repartiront a la prochaine synchronisation, automatique ou manuelle." & _
               vbCrLf & vbCrLf & "Adresse essayee: " & ApiBase() & vbCrLf & note, _
               vbExclamation, "SLCC"
    End If
End Sub


'' ------------------------------------------------------- synchro automatique

'' Excel calls these two for a standard module when the file opens and closes.
'' The usual Workbook_Open lives in ThisWorkbook, which this project cannot bind
'' to: see SheetByName.
Public Sub Auto_Open()
    ArmAutoSync
End Sub

Public Sub Auto_Close()
    DisarmAutoSync
End Sub

Public Sub ArmAutoSync()
    On Error Resume Next
    DisarmAutoSync
    '' Qualified with the file name: an unqualified OnTime can land in another
    '' open workbook that happens to define the same procedure.
    gTarget = "'" & ActiveSheet.Parent.Name & "'!SlccAutoSync"
    gTick = CDbl(Now) + AUTO_MINUTES / 1440#
    Application.OnTime CDate(gTick), gTarget
End Sub

Public Sub DisarmAutoSync()
    On Error Resume Next
    If gTick > 0 And Len(gTarget) > 0 Then
        Application.OnTime CDate(gTick), gTarget, , False
    End If
    gTick = 0
End Sub

'' The unattended push.
''
'' Silent by construction. An operator typing a line must never be interrupted
'' by a dialog they did not ask for, and a failed push is not their problem: the
'' banner records it and the next tick tries again. Excel defers OnTime while a
'' cell is being edited, so this cannot land mid-keystroke either.
Public Sub SlccAutoSync()
    Dim ws As Worksheet, book As Workbook
    Dim sent As Long, ignored As Long, note As String
    Dim ok As Boolean

    If gBusy Then Exit Sub
    gBusy = True
    On Error Resume Next

    Set book = ActiveSheet.Parent
    If Not book Is Nothing Then
        For Each ws In book.Worksheets
            If IsOperationalSheet(ws) Then
                ok = PushSheet(ws, sent, ignored, note)
                StampFreshness ws, ok, sent
                '' One unreachable call means the server is down, not that this
                '' sheet is special. Trying the six others would freeze Excel for
                '' six more connection timeouts.
                If Not ok Then Exit For
            End If
        Next ws
    End If

    gBusy = False
    ArmAutoSync
End Sub

'' Say, on the sheet itself, how fresh the mirror is.
''
'' The operator cannot see the website, and the website is what management
'' reads. If the push has been failing since this morning, the sheet in front of
'' them is the only place that can say so.
Public Sub StampFreshness(ws As Worksheet, ByVal ok As Boolean, ByVal sent As Long)
    Dim label As String
    On Error Resume Next
    ws.Unprotect
    If ok Then
        label = "SLCC a jour - derniere synchro " & Format$(Now, "dd/mm/yyyy hh:nn")
        If sent > 0 Then label = label & "   " & sent & " ligne(s) envoyee(s)"
        ws.Cells(FRESH_ROW, 1).Font.Color = RGB(31, 106, 92)
    Else
        label = "SLCC injoignable - essai " & Format$(Now, "dd/mm/yyyy hh:nn") & _
                "   les lignes validees partiront a la prochaine tentative"
        ws.Cells(FRESH_ROW, 1).Font.Color = RGB(155, 28, 28)
    End If
    ws.Cells(FRESH_ROW, 1).Value = label
    ProtectSheet ws
End Sub


'' One row as JSON, headers becoming keys. Kept deliberately dumb: the backend
'' validates every field again, so the workbook only has to be honest about
'' what the cells contain.
Private Function RowToJson(ws As Worksheet, ByVal r As Long) As String
    Dim c As Long, last As Long, out As String, key As String, cellText As String
    last = LastHeaderColumn(ws)
    out = "{"
    For c = 1 To last
        key = LCase$(Trim$(CStr(ws.Cells(HEADER_ROW, c).Value)))
        If Len(key) > 0 Then
            cellText = CStr(ws.Cells(r, c).Text)
            If Len(out) > 1 Then out = out & ","
            out = out & """" & JsonEscape(key) & """:""" & JsonEscape(cellText) & """"
        End If
    Next c
    out = out & ",""source_row"":" & r
    RowToJson = out & "}"
End Function


'' Ask SLCC to check a code and sign the line.
''
'' Returns the signature, or "" with `refusal` explaining why. The code is sent
'' once, over the API, and is never written anywhere in this workbook.
Public Function RequestValidationToken(ByVal sheetName As String, ByVal syncId As String, _
                                       ByVal maker As String, ByVal checker As String, _
                                       ByVal code As String, ByRef refusal As String) As String
    Dim payload As String, body As String, failure As String
    Dim httpStatus As Long
    Dim tokenStart As Long, tokenEnd As Long

    refusal = ""
    payload = "{""sheet"":""" & JsonEscape(sheetName) & """,""sync_id"":""" & JsonEscape(syncId) & _
              """,""maker"":""" & JsonEscape(maker) & """,""checker"":""" & JsonEscape(checker) & _
              """,""code"":""" & JsonEscape(code) & """}"

    If Not SlccRequest("POST", ApiBase() & "/excel/validate", payload, httpStatus, body, failure) Then
        GoTo Offline
    End If

    If httpStatus < 200 Or httpStatus >= 300 Then
        refusal = "SLCC a repondu " & httpStatus & "."
        Exit Function
    End If
    If InStr(body, """accepted"":true") = 0 Then
        refusal = ExtractJson(body, "reason")
        If Len(refusal) = 0 Then refusal = "validation refusee par SLCC."
        Exit Function
    End If

    RequestValidationToken = ExtractJson(body, "token")
    If Len(RequestValidationToken) = 0 Then refusal = "SLCC n'a pas renvoye de jeton."
    Exit Function

Offline:
    refusal = "SLCC injoignable (" & ApiBase() & ")." & vbCrLf & _
              "La validation exige une connexion: c'est le serveur qui verifie le code."
End Function

'' Pull one string field out of a small JSON reply. Enough for two known keys.
Private Function ExtractJson(ByVal body As String, ByVal key As String) As String
    Dim marker As String, start As Long, finish As Long
    marker = """" & key & """:"""
    start = InStr(body, marker)
    If start = 0 Then Exit Function
    start = start + Len(marker)
    finish = InStr(start, body, """")
    If finish = 0 Then Exit Function
    ExtractJson = Mid$(body, start, finish - start)
End Function

Public Function JsonEscape(ByVal s As String) As String
    s = Replace(s, "\", "\\")
    s = Replace(s, """", "\""")
    s = Replace(s, vbCrLf, " ")
    s = Replace(s, vbCr, " ")
    s = Replace(s, vbLf, " ")
    s = Replace(s, vbTab, " ")
    JsonEscape = s
End Function

'' Pull the live stock back from SLCC into ARTICLES.
''
'' The workbook is where the work is entered; the database is what knows the
'' stock. This asks the server for the current figures rather than computing
'' anything locally - there is no second stock logic in this file.
Public Sub VerifierConnexionSLCC(Optional control As Object)
    Dim ws As Worksheet
    Dim body As String, failure As String, httpStatus As Long

    Set ws = SheetByName("ARTICLES")
    If ws Is Nothing Then Exit Sub

    If Not SlccRequest("GET", ApiBase() & "/excel/status", "", httpStatus, body, failure) Then
        GoTo Offline
    End If

    If httpStatus < 200 Or httpStatus >= 300 Then
        MsgBox "SLCC a repondu " & httpStatus & ".", vbExclamation, "SLCC"
        Exit Sub
    End If

    MsgBox "SLCC est joignable." & vbCrLf & vbCrLf & _
           "Ce bouton verifie la connexion, il ne rafraichit rien." & vbCrLf & _
           "Le stock affiche dans ARTICLES est une photo datee: pour la" & vbCrLf & _
           "rafraichir, telechargez la derniere version depuis la page" & vbCrLf & _
           "Fichier operationnel du site.", vbInformation, "SLCC"
    Exit Sub

Offline:
    MsgBox "SLCC injoignable." & vbCrLf & _
           "Adresse essayee: " & ApiBase() & vbCrLf & failure, vbExclamation, "SLCC"
End Sub
'''


_HTTP = r'''
Option Explicit

'' One HTTP layer for the whole workbook.
''
'' Microsoft 365 disables ActiveX by default, which makes CreateObject fail
'' with error 429 even though msxml6.dll is registered and present. Relying on
'' it alone meant every button died on a stock install, so this module tries
'' the COM objects first - they are faster and synchronous - and falls back to
'' PowerShell when Office refuses them.

#If VBA7 Then
    Private Declare PtrSafe Sub SleepMs Lib "kernel32" Alias "Sleep" (ByVal ms As Long)
#Else
    Private Declare Sub SleepMs Lib "kernel32" Alias "Sleep" (ByVal ms As Long)
#End If

'' Seconds to wait for the shelled-out call before giving up.
Private Const SHELL_TIMEOUT As Long = 40

'' ProgIDs in order of preference. The first Office allows wins.
Private Function NewHttp() As Object
    Dim ids As Variant, i As Long, obj As Object
    ids = Array("MSXML2.ServerXMLHTTP.6.0", "MSXML2.ServerXMLHTTP", _
                "WinHttp.WinHttpRequest.5.1", "MSXML2.XMLHTTP.6.0", "MSXML2.XMLHTTP")
    For i = LBound(ids) To UBound(ids)
        On Error Resume Next
        Set obj = CreateObject(CStr(ids(i)))
        On Error GoTo 0
        If Not obj Is Nothing Then
            Set NewHttp = obj
            Exit Function
        End If
    Next i
    Set NewHttp = Nothing
End Function

'' True when the call went through. `status` and `body` carry the answer;
'' `failure` explains why nothing came back.
Public Function SlccRequest(ByVal method As String, ByVal url As String, _
                            ByVal payload As String, ByRef status As Long, _
                            ByRef body As String, ByRef failure As String) As Boolean
    Dim http As Object

    status = 0
    body = ""
    failure = ""

    Set http = NewHttp()
    If Not http Is Nothing Then
        On Error GoTo ComFailed
        http.Open method, url, False
        If Len(payload) > 0 Then
            http.setRequestHeader "Content-Type", "application/json; charset=utf-8"
            http.send payload
        Else
            http.send
        End If
        status = http.status
        body = http.responseText
        SlccRequest = True
        Exit Function
    End If

    '' Office blocked every ActiveX object: go through the shell instead.
    SlccRequest = ShellRequest(method, url, payload, status, body, failure)
    Exit Function

ComFailed:
    '' The object was created but the call itself failed - the server is
    '' unreachable, not blocked. Say so rather than retrying the same way.
    failure = "SLCC injoignable (" & Err.Description & ")"
    SlccRequest = False
End Function

'' PowerShell does the call; VBA reads the answer from a file.
''
'' The payload travels through a file rather than the command line: a sync of
'' twenty rows already exceeds what a command line accepts, and quoting JSON
'' inside a shell string is a bug waiting to happen.
Private Function ShellRequest(ByVal method As String, ByVal url As String, _
                              ByVal payload As String, ByRef status As Long, _
                              ByRef body As String, ByRef failure As String) As Boolean
    Dim stem As String, reqFile As String, respFile As String, doneFile As String
    Dim command As String, script As String
    Dim handle As Integer, waited As Single, line As String

    stem = Environ$("TEMP") & "\slcc_" & Format$(Now, "yyyymmddhhnnss") & "_" & CLng(Timer * 100)
    reqFile = stem & "_req.json"
    respFile = stem & "_resp.txt"
    doneFile = stem & "_done.txt"

    If Len(payload) > 0 Then
        handle = FreeFile
        Open reqFile For Output As #handle
        Print #handle, payload
        Close #handle
    End If

    script = "$ErrorActionPreference='Stop';" & _
             "try{" & _
             "$h=@{'Content-Type'='application/json; charset=utf-8'};" & _
             "if('" & method & "' -eq 'GET'){" & _
             "$r=Invoke-WebRequest -Uri '" & url & "' -Method GET -UseBasicParsing" & _
             "}else{" & _
             "$b=[System.IO.File]::ReadAllText('" & reqFile & "',[System.Text.Encoding]::Default);" & _
             "$r=Invoke-WebRequest -Uri '" & url & "' -Method " & method & _
             " -Headers $h -Body $b -UseBasicParsing};" & _
             "$s=[int]$r.StatusCode;$t=$r.Content" & _
             "}catch{" & _
             "$s=0;$t=$_.Exception.Message;" & _
             "if($_.Exception.Response){$s=[int]$_.Exception.Response.StatusCode;" & _
             "$sr=New-Object IO.StreamReader($_.Exception.Response.GetResponseStream());" & _
             "$t=$sr.ReadToEnd()}};" & _
             "[System.IO.File]::WriteAllText('" & respFile & "'," & _
             "$s.ToString()+[Environment]::NewLine+$t,[System.Text.Encoding]::Default);" & _
             "[System.IO.File]::WriteAllText('" & doneFile & "','1')"

    command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -Command """ & _
              Replace(script, """", "\""") & """"

    On Error GoTo ShellFailed
    Shell command, vbHide

    '' Shell is asynchronous, so wait for the marker file the script writes last.
    waited = 0
    Do While Len(Dir$(doneFile)) = 0
        SleepMs 200
        DoEvents
        waited = waited + 0.2
        If waited > SHELL_TIMEOUT Then
            failure = "SLCC n'a pas repondu en " & SHELL_TIMEOUT & " secondes."
            KillQuiet reqFile
            ShellRequest = False
            Exit Function
        End If
    Loop

    handle = FreeFile
    Open respFile For Input As #handle
    If Not EOF(handle) Then
        Line Input #handle, line
        status = CLng(Val(line))
    End If
    Do While Not EOF(handle)
        Line Input #handle, line
        body = body & line
    Loop
    Close #handle

    KillQuiet reqFile
    KillQuiet respFile
    KillQuiet doneFile

    If status = 0 Then
        failure = "SLCC injoignable. " & Left$(body, 200)
        ShellRequest = False
        Exit Function
    End If

    ShellRequest = True
    Exit Function

ShellFailed:
    failure = "Impossible de contacter SLCC (" & Err.Description & ")."
    ShellRequest = False
End Function

Private Sub KillQuiet(ByVal path As String)
    On Error Resume Next
    If Len(Dir$(path)) > 0 Then Kill path
    On Error GoTo 0
End Sub
'''


#: Modules, in the order they are added to the project.
MODULES: tuple[tuple[str, str], ...] = (
    ("modHash", _SHA256),
    ("modHttp", _HTTP),
    ("modWorkflow", _WORKFLOW),
    ("modSync", _SYNC),
)


def module_sources() -> list[tuple[str, str]]:
    """(name, source) for each module, ready to be compiled."""
    return [(name, source.strip() + "\r\n") for name, source in MODULES]