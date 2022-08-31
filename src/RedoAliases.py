import string 
import FreeCAD

__title__    = 'Redo_aliases'
__author__   = 'Will Dickson'
__version__  = '0.1.01'
__date__     = '2022-08-30'
__Comment__  = 'Tempory kludge to deal with spreadsheet row insertion bug'
__Status__   = 'stable'
__Requires__ = 'FreeCAD 0.19'


# Array of cels to redo
num_rows = 100
num_cols = 2 
max_cols = len(string.ascii_uppercase)

FreeCAD.Console.PrintMessage(f'Redoing aliases \n') 
FreeCAD.Console.PrintMessage(f'num_rows = {num_rows}\n') 
FreeCAD.Console.PrintMessage(f'num_cols = {num_cols}\n') 

if num_cols > max_cols: 
    FreeCAD.Console.PrintError(f'too many columns, must <= {max_cols}\n') 

for i in range(1,num_rows+1):
    for j in range(num_cols):
        cell_str = f'{string.ascii_uppercase[j]}{i}'
        cell_alias = App.ActiveDocument.Spreadsheet.getAlias(cell_str)
        if cell_alias is not None:
            App.ActiveDocument.Spreadsheet.setAlias(cell_str, f'{cell_alias}_')
            App.ActiveDocument.Spreadsheet.setAlias(cell_str, f'{cell_alias}')
App.ActiveDocument.Spreadsheet.recompute()










