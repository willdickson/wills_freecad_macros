"""
SyncSpreadsheetAliases.py 

Simple macro which synchronizes the aliases in a spreadsheet after they
they've been scrambled due to row/column insertion deletions. 

This is a temporary kludge which I came up with to deal with a bug in the
current FreeCAD version (0.20) which can cause the aliases to become out of
sync when inserting/deleting rows and columns.  

"""
import string 
import FreeCAD
import xml.etree.ElementTree as ET

__title__    = 'SyncSpreadsheetAliases'
__author__   = 'Will Dickson'
__version__  = '0.1.01'
__date__     = '2022-08-30'
__Comment__  = 'Tempory kludge to deal with spreadsheet row insertion bug'
__Status__   = 'stable'
__Requires__ = 'FreeCAD 0.19'

FreeCAD.Console.PrintMessage(f'synchronizing spreadsheet aliases\n') 

cells_xml_root = ET.fromstring(App.ActiveDocument.Spreadsheet.cells.Content)
tmp_suffix = '__tmp__'

for cell in cells_xml_root.findall('Cell'):
    if 'alias' in cell.attrib:
        address = cell.attrib['address']
        alias = cell.attrib['alias']
        FreeCAD.Console.PrintMessage(f'{address} alias {alias}\n') 
        App.ActiveDocument.Spreadsheet.setAlias(address, f'{alias}{tmp_suffix}') 
        App.ActiveDocument.Spreadsheet.setAlias(address, alias)

App.ActiveDocument.Spreadsheet.recompute()
FreeCAD.Console.PrintMessage('done\n') 


