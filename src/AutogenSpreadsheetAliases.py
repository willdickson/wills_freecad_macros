"""
AutogenSpreadsheetAliases.py 

Simple macro automatically generates spreadsheet aliases in a design
spreadsheet.  The text strings in column A are used to generate the aliases
for column B.  Aliases are only generated in cases where both column B and
column B have values set. 
"""
import string 
import FreeCAD
import xml.etree.ElementTree as ET


__title__    = 'AutogenSpreadsheetAliases'
__author__   = 'Will Dickson'
__version__  = '0.1.01'
__date__     = '2022-08-30'
__Comment__  = 'Tempory kludge to deal with spreadsheet row insertion bug'
__Status__   = 'stable'
__Requires__ = 'FreeCAD 0.19'


def get_column_list(column_name, cells_list):
    """
    Returns list of cells with content from column with given name.
    """
    column_list = []
    for cell in cells_list:
        if cell.attrib['address'].startswith(column_name):
            if cell.attrib['address'][len(column_name)] in string.digits:
                if 'content' in cell.attrib:
                    column_list.append(cell)
    return column_list


def get_row_from_address(address):
    """
    Returns the row number and an integer given an address string.
    """
    row = None
    for i in range(len(address)):
        if address[i:].isdigit():
            row = int(address[i:]) 
            break
    return row

# -----------------------------------------------------------------------------

FreeCAD.Console.PrintMessage(f'autogenerating spreadsheet aliases\n') 
cells_xml_root = ET.fromstring(App.ActiveDocument.Spreadsheet.cells.Content)
cells_list = cells_xml_root.findall('Cell')

column_a_list = get_column_list('A', cells_list)
column_b_list = get_column_list('B', cells_list)

for a_cell in column_a_list:
    a_address = a_cell.attrib['address']
    a_content = a_cell.attrib['content']
    if a_content[0] == '\'':
        a_content = a_content[1:]
    a_row = get_row_from_address(a_address)
    for b_cell in column_b_list:
        b_address = b_cell.attrib['address']
        b_row = get_row_from_address(b_address)
        if a_row == b_row:
            FreeCAD.Console.PrintMessage(f'{b_address} alias {a_content}\n') 
            App.ActiveDocument.Spreadsheet.setAlias(b_address, a_content)

App.ActiveDocument.Spreadsheet.recompute()
FreeCAD.Console.PrintMessage('done\n') 

