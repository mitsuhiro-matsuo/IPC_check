Attribute VB_Name = "Module1"
Option Explicit

Sub 変換()

Dim ws As Worksheet
Dim t1 As Integer
Dim endt As Integer

Dim M1 As String
Dim M2 As String
Dim M3 As String
Dim SRASSHUITI As String
Dim toru As String
Dim keta2 As String
Dim keta3 As String


Set ws = Worksheets("対象")

Range("C1048576").Select
    Selection.End(xlUp).Select

endt = Selection.Row

For t1 = 2 To endt

    M1 = ""
    M2 = ""
    M3 = ""
    
    ws.Cells(t1, 3).Select
    M1 = Left(ws.Cells(t1, 3), 4)
    
    
    SRASSHUITI = InStr(ws.Cells(t1, 3), "/")
    
    toru = SRASSHUITI - 5
    
    M2 = Mid(ws.Cells(t1, 3), 5, toru)
    M2 = Replace(M2, " ", "")
    
    keta2 = Len(M2)
    
    
    Select Case keta2
    
        Case 1
            
            M2 = "000" & M2
            
        Case 2
        
            M2 = "00" & M2
            
        Case 3
            
            M2 = "0" & M2
        
    End Select
    
    
    
    M3 = Mid(ws.Cells(t1, 3), SRASSHUITI + 1)
    M3 = Replace(M3, " ", "")
    
    keta3 = Len(M3)
    
      Select Case keta3
    
        Case 1
            
            M3 = M3 & "00000"
            
        Case 2
        
            M3 = M3 & "0000"
            
        Case 3
            
            M3 = M3 & "000"
        
        Case 4
            
            M3 = M3 & "00"
            
        Case 5
            
            M3 = M3 & "0"
        
    End Select
    
    ws.Cells(t1, 4) = M1 & M2 & M3


Next t1

Call 現行IPCとの照合
Call 改正IPCとの照合
Call 対象が改正IPCと一致したもの抜粋
Call 改正IPC抜粋改正後IPCの内容追記

End Sub


Sub 変換2()


Dim ws As Worksheet
Dim t1 As Long
Dim endt As Long

Dim M1 As String
Dim M2 As String
Dim M3 As String
Dim SRASSHUITI As String
Dim toru As String
Dim keta2 As Integer
Dim keta3 As Integer
Dim keta1 As Integer



Set ws = Worksheets("現行IPC")

Range("B1048576").Select
    Selection.End(xlUp).Select

endt = Selection.Row

For t1 = 2 To endt

    Application.StatusBar = t1 & "/" & endt
    
    M1 = ""
    M2 = ""
    M3 = ""
    
    'ws.Cells(t1, 2).Select
    M1 = Left(ws.Cells(t1, 2), 4)
    
    keta1 = Len(ws.Cells(t1, 2))
    
    If keta1 > 4 Then
           
        
        SRASSHUITI = InStr(ws.Cells(t1, 2), "/")
        
        toru = SRASSHUITI - 5
        
        M2 = Mid(ws.Cells(t1, 2), 5, toru)
        M2 = Replace(M2, " ", "")
        
        keta2 = Len(M2)
        
        
        Select Case keta2
        
            Case 1
                
                M2 = "000" & M2
                
            Case 2
            
                M2 = "00" & M2
                
            Case 3
                
                M2 = "0" & M2
            
        End Select
        
        
        
        M3 = Mid(ws.Cells(t1, 2), SRASSHUITI + 1)
        M3 = Replace(M3, " ", "")
        
        keta3 = Len(M3)
        
          Select Case keta3
        
            Case 1
                
                M3 = M3 & "00000"
                
            Case 2
            
                M3 = M3 & "0000"
                
            Case 3
                
                M3 = M3 & "000"
            
            Case 4
                
                M3 = M3 & "00"
                
            Case 5
                
                M3 = M3 & "0"
            
        End Select
    
    End If
        
    ws.Cells(t1, 5) = M1 & M2 & M3


Next t1


End Sub

Sub 現行IPCとの照合()


Dim ws1 As Worksheet '対象シート
Dim ws2 As Worksheet '現行IPCシート
Dim t1 As Long
Dim t2 As Long
Dim endt1 As Long
Dim endt2 As Long

Dim taisyou1 As String
Dim taisyou2 As String

Set ws1 = Worksheets("対象")
Set ws2 = Worksheets("現行IPC")

ws1.Activate

ws1.Range("C1048576").Select
    Selection.End(xlUp).Select
endt1 = Selection.Row

ws2.Activate

ws2.Range("B1048576").Select
    Selection.End(xlUp).Select
endt2 = Selection.Row

ws1.Activate

For t1 = 2 To endt1

ws1.Cells(t1, 3).Select

Application.StatusBar = t1 & "/" & endt1

taisyou1 = ws1.Cells(t1, 4)

    For t2 = 2 To endt2
    
        taisyou2 = ws2.Cells(t2, 5)
        
        
        If taisyou1 = taisyou2 Then
        
        ws1.Cells(t1, 5) = "*"
        
        Exit For
        
        
        End If


    Next t2
    
Next t1

'MsgBox "現行IPCと照合終了しました。"

End Sub

Sub 改正IPCとの照合()


Dim ws1 As Worksheet '対象シート
Dim ws2 As Worksheet '改正シート
Dim t1 As Long
Dim t2 As Long
Dim endt1 As Long
Dim endt2 As Long

Dim taisyou1 As String
Dim taisyou2 As String

Set ws1 = Worksheets("対象")
Set ws2 = Worksheets("改正IPC")

ws1.Activate

ws1.Range("C1048576").Select
    Selection.End(xlUp).Select
endt1 = Selection.Row

ws2.Activate

ws2.Range("C1048576").Select
    Selection.End(xlUp).Select
endt2 = Selection.Row

ws1.Activate

For t1 = 2 To endt1

ws1.Cells(t1, 3).Select

Application.StatusBar = t1 & "/" & endt1

taisyou1 = ws1.Cells(t1, 4)

    For t2 = 2 To endt2
    
        taisyou2 = ws2.Cells(t2, 3)
        
        
        If taisyou1 = taisyou2 Then
        
        ws1.Cells(t1, 6) = "*"
        
        Exit For
        
        
        End If


    Next t2
    
Next t1

'MsgBox "改正IPCと照合終了しました。"

End Sub


Sub 対象が改正IPCと一致したもの抜粋()

Dim ws1 As Worksheet '対象シート
Dim ws2 As Worksheet '改正IPC
Dim ws3 As Worksheet '対象が改正IPCと一致したものの抜粋シート

Dim t1 As Long
Dim t2 As Long
Dim t3 As Long

Dim endt1 As Long
Dim endt2 As Long

Dim taisyou1 As String
Dim taisyou2 As String

Set ws1 = Worksheets("対象")
Set ws2 = Worksheets("改正IPC")
Set ws3 = Worksheets("対象が改正IPCと一致したものの抜粋")

ws1.Activate

ws1.Range("C1048576").Select
    Selection.End(xlUp).Select
endt1 = Selection.Row

ws2.Activate

ws2.Range("C1048576").Select
    Selection.End(xlUp).Select
endt2 = Selection.Row


ws1.Activate

t3 = 2

ws3.Activate

ws3.Rows("2:2").Select
ws3.Range(Selection, Selection.End(xlDown)).Select
Selection.Delete Shift:=xlUp
Range("A1").Select

For t1 = 2 To endt1

'ws1.Cells(t1, 3).Select

Application.StatusBar = t1 & "/" & endt1

taisyou1 = ws1.Cells(t1, 4)

    For t2 = 2 To endt2
    
        taisyou2 = ws2.Cells(t2, 3)
        
        
        If taisyou1 = taisyou2 Then
        
           ws2.Activate
                
            ws2.Range(ws2.Cells(t2, 1), ws2.Cells(t2, 6)).Select
            ws2.Range(ws2.Cells(t2, 1), ws2.Cells(t2, 6)).Copy
            
            ws3.Activate

            ws3.Cells(t3, 1).Select
            ws3.Cells(t3, 1).PasteSpecial
                    
            ws2.Activate
            
            ws2.Cells(t2, 7).Select
            ws2.Cells(t2, 7).Copy
            
            ws3.Activate

            ws3.Cells(t3, 8).Select
            ws3.Cells(t3, 8).PasteSpecial
                                            
            ws1.Activate
            
            ws1.Cells(t1, 2).Select
            ws1.Cells(t1, 2).Copy
             
            ws3.Activate

            ws3.Cells(t3, 9).Select
            ws3.Cells(t3, 9).PasteSpecial
            
            ws1.Activate
            
            ws1.Cells(t1, 3).Select
            ws1.Cells(t1, 3).Copy
             
            ws3.Activate

            ws3.Cells(t3, 10).Select
            ws3.Cells(t3, 10).PasteSpecial

                        
            t3 = t3 + 1
        
        End If
        
                                 
    Next t2
    
Next t1

   ws3.Cells(1, 1).Select
   Selection.CurrentRegion.Select
   Selection.Borders.LineStyle = xlContinuous

    ws3.Cells(1, 1).Select

'MsgBox "改正IPC抜粋作業終了しました"

Application.StatusBar = False


End Sub


Sub 対象シートクリア()

Dim ws1 As Worksheet '対象シート
Set ws1 = Worksheets("対象")

ws1.Activate

ws1.Rows("2:2").Select
ws1.Range(Selection, Selection.End(xlDown)).Select
    Selection.Delete Shift:=xlUp
ws1.Range("A1").Select

End Sub

Sub 改正IPC抜粋改正後IPCの内容追記()

Dim ws3 As Worksheet '対象が改正IPCと一致したものの抜粋シート
Dim ws4 As Worksheet '現行IPC

Dim t3 As Long
Dim t4 As Long

Dim endt3 As Long
Dim endt4 As Long

Dim taisyou41 As String
Dim taisyou42 As String

Set ws3 = Worksheets("対象が改正IPCと一致したものの抜粋")
Set ws4 = Worksheets("現行IPC")


ws3.Range("E1048576").Select
    Selection.End(xlUp).Select
endt3 = Selection.Row

ws4.Activate

ws4.Range("E1048576").Select
    Selection.End(xlUp).Select
endt4 = Selection.Row

t3 = 2

For t3 = 2 To endt3

Application.StatusBar = t3 & "/" & endt3

taisyou41 = ws3.Cells(t3, 5) '抜粋のmodificatio2
  
    t4 = 2
 
    For t4 = 2 To endt4
                 
    taisyou42 = ws4.Cells(t4, 5) '現行IPCの照合用IPC
                      
        If taisyou41 = taisyou42 Then
        
            'ws4.Activate
            'ws4.Cells(t4, 4).Select
            'ws4.Cells(t4, 4).Copy
            
            'ws3.Activate
            'ws3.Cells(t3, 7).Select
            'ws3.Cells(t3, 7).PasteSpecial
            't3 = t3 + 1
            
            If ws3.Cells(t3, 7) = "" Then
                        
                ws3.Cells(t3, 7) = ws4.Cells(t4, 4)
            
            Else
                         
                ws3.Cells(t3, 7) = ws3.Cells(t3, 7) & "★" & ws4.Cells(t4, 4)
            
            End If
                                   
        End If
                              
Next t4
    
Next t3

ws3.Activate

   ws3.Cells(1, 1).Select
   Selection.CurrentRegion.Select
   Selection.Borders.LineStyle = xlContinuous

    ws3.Cells(1, 1).Select

MsgBox "改正IPC抜粋作業終了しました"

Application.StatusBar = False


End Sub



























































