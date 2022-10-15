"""
A2PlusAssemblyToMujoco.py 

Macro to automatically convert an assembly of a mechanical model made
in the A2Plus workbench to a mujoco xml file. 

Notes:
Currently in development.  May require annotating the A2Plus assembly and
or the source files in some fashion to help specify where the joints are
locate, what kind of joint they are etc. 

"""
import os
import re
import string 
import collections
import xml.dom.minidom
import xml.etree.ElementTree as ET
import Mesh
import FreeCAD
from PySide import QtGui
from PySide import QtCore

__title__    = 'A2PlusAssemblyToMujoco'
__author__   = 'Will Dickson'
__version__  = '0.1.01'
__date__     = '2022-09-07'
__Comment__  = 'Convert machine assemblies made in A2Plus to mujoco xml'
__Status__   = 'unstable'
__Requires__ = 'FreeCAD 0.19'

MESH_FILE_DIR = 'mesh_files'
MUJOCO_MODEL_FILE = 'model.xml'

COMPILER_ATTRIB = {
        'coordinate' : 'global'
        }

OPTION_ATTRIB = {
        'gravity'  : '0 0 -1',
        'timestep' : '0.005',
        }

FLOOR_ATTRIB = { 
        'name'     : 'floor', 
        'size'     : '0 0 .05',  
        'type'     : 'plane',  
        'material' : 'grid',  
        'condim'   : '3', 
        }

GRID_TEXTURE_ATTRIB = { 
        'name'    : 'grid',  
        'type'    : '2d', 
        'builtin' : 'checker',  
        'width'   : '512',  
        'height'  : '512',  
        'rgb1'    : '0.1 0.2 0.3',  
        'rgb2'    : '0.2 0.3 0.4', 
        }

GRID_MATERIAL_ATTRIB = { 
        'name'        : 'grid',  
        'texture'     : 'grid',  
        'texrepeat'   : '10 10',  
        'texuniform'  : 'true',  
        'reflectance' : '.2',
        }

LIGHT_ATTRIB = { 
        'name'     : 'spotlight', 
        'mode'     : 'targetbodycom', 
        'target'   : 'base',  
        'diffuse'  : '0.8 0.8 0.8',  
        'specular' : '0.2 0.2 0.2',  
        }

def get_part_info():
    """
    Extracts part information, e.g., postion, rotation, source file.
    """
    app_doc = App.ActiveDocument
    gui_doc = FreeCADGui.getDocument(App.ActiveDocument.Name)
    part_info = {}
    for part in app_doc.findObjects(Type='Part::FeaturePython'):
        p = part.Placement.Base
        q = part.Placement.Rotation
        axis = part.Placement.Rotation.Axis
        angle = part.Placement.Rotation.Angle
        _, src_file = os.path.split(part.sourceFile)
        name, _ = os.path.splitext(src_file)
        shape_color = gui_doc.getObject(part.Name).ShapeColor
        part_info[part.Name] = {
                'pos'        : p, 
                'quat'       : q, 
                'axis'       : axis,
                'angle'      : angle,
                'part_label' : part.Label,
                'part_name'  : name, 
                'part_file'  : src_file,
                'part_obj'   : part,
                'part_color' : shape_color,
                }
    return part_info


def get_save_info():
    active_doc_dir, active_doc_file = os.path.split(App.ActiveDocument.FileName)
    save_dir = select_save_dir_dialog()
    mesh_dir = os.path.join(save_dir, MESH_FILE_DIR)
    save_info = {
            'active_doc_dir'  : active_doc_dir, 
            'active_doc_file' : active_doc_file, 
            'save_dir'        : save_dir,
            'mesh_dir'        : mesh_dir,
            }
    return save_info


def select_save_dir_dialog():
    """
    Opens dialog asking for the directory where the mujoco files will be saved.
    """
    default_dir = QtCore.QDir.home().path()
    default_dir = os.path.join(default_dir, 'tmp', 'a2plus_mujoco_test')
    save_to_dir = QtGui.QFileDialog.getExistingDirectory(
            parent = None, 
            caption = 'Select Save Directory', 
            dir = default_dir, 
            )
    return save_to_dir 


def get_mesh_file(part_name):
    mesh_file = f'{part_name}.stl'
    return mesh_file


def create_mesh_files(part_info, save_info):
    """
    Creates an stl file for each part in the part_info and saves it to the
    sub-directory MESH_FILE_DIR of the saveto_dir in the save_info. 
    """
    mesh_dir = save_info['mesh_dir']
    os.makedirs(mesh_dir, exist_ok=True)
    msg = f'saving mesh files to: {mesh_dir}'
    fc_print(msg)

    for item, data in part_info.items():
        part_file = os.path.join(save_info['active_doc_dir'], data['part_file'])
        part_name = data['part_name']
        part_obj = data['part_obj']
        mesh_file = os.path.join(mesh_dir, get_mesh_file(part_name))
        fc_print(f'saving:  {mesh_file}')

        # Open document and save .stl file
        FreeCAD.openDocument(part_file)
        App.setActiveDocument(part_name)
        doc = App.getDocument(part_name)
        last_feature_obj = doc.findObjects(Type="PartDesign::Feature")[-1]
        Mesh.export([last_feature_obj], mesh_file)
        App.closeDocument(part_name)


def create_mujoco_xml_file(part_info, save_info):
    """
    Creates the mujoco xml file.
    """

    # Create element tree  
    root_elem = ET.Element('mujoco')
    ET.SubElement(root_elem, 'compiler', attrib=COMPILER_ATTRIB)
    ET.SubElement(root_elem, 'option', attrib=OPTION_ATTRIB)

    add_assets(root_elem, part_info)
    add_bodies(root_elem, part_info)
    add_equalities(root_elem, part_info)
    add_actuators(root_elem, part_info)

    # Save mujoco model to pretty printed xml file
    xml_str = ET.tostring(root_elem)
    xml_str = xml.dom.minidom.parseString(xml_str).toprettyxml(indent='  ')
    save_dir = save_info['save_dir']
    mujoco_file = os.path.join(save_dir, MUJOCO_MODEL_FILE)
    with open(mujoco_file, 'w') as f:
        f.write(xml_str)


def add_assets(root_elem, part_info):
    """
    Adds the assets element and all sub elements to the element tree
    """
    asset_elem = ET.SubElement(root_elem, 'asset') 
    for item, data in part_info.items():
        part_name = data['part_name']
        mesh_file = os.path.join('.', MESH_FILE_DIR, get_mesh_file(part_name))
        mesh_attrib = {'file' : mesh_file}
        ET.SubElement(asset_elem, 'mesh', attrib=mesh_attrib)

    # Add material elements for colors 
    color_list = list({data['part_color'] for item, data in part_info.items()})
    for index, color in enumerate(color_list):
        color_name = f'color_{index}'
        color_vals = ' '.join([f'{val:1.2f}' for val in color])
        color_attrib = {'name': color_name, 'rgba': color_vals} 
        ET.SubElement(asset_elem, 'material', attrib=color_attrib)

    # Create mapping from part keys to color names
    part_to_color_name = {}
    for item, data in part_info.items():
        index = color_list.index(data['part_color'])
        color_name = f'color_{index}'
        part_to_color_name[item] = color_name

    # Add texture and material elements for grid
    ET.SubElement(asset_elem, 'texture', attrib=GRID_TEXTURE_ATTRIB)
    ET.SubElement(asset_elem, 'material', attrib=GRID_MATERIAL_ATTRIB)


def add_bodies(root_elem, part_info):
    """
    Adds the top level worldbody element and all subelements to the element
    tree.
    """

    # Add worldbody element
    worldbody_elem = ET.SubElement(root_elem, 'worldbody')

    # Add floor
    ET.SubElement(worldbody_elem, 'geom', attrib=FLOOR_ATTRIB)

    # Add light
    # TODO:  use bounding boxes information to extract light positions
    xvals, yvals, zvals = get_xyz_extent(part_info)
    xmin, xmax = xvals
    ymin, ymax = yvals
    zmin, zmax = zvals
    xpos = 0
    ypos = 1.5*ymax
    zpos = 1.5*zmax
    cutoff = 2*max([xmax, ymax, zmax])
    light_attrib = dict(LIGHT_ATTRIB)
    light_attrib['pos'] = f'{xpos}, {ypos},{zpos}'
    light_attrib['cutoff'] = f'{cutoff}' 
    ET.SubElement(worldbody_elem, 'light', attrib=LIGHT_ATTRIB)


def add_equalities(root_elem, part_info):
    pass


def add_actuators(root_elem, part_info):
    pass


def get_xyz_extent(part_info):
    """
    Computs the min and max x, y and z values for all parts in the assembly.
    """
    x_list = []
    y_list = []
    z_list = []
    for item, data in part_info.items():
        bbox = data['part_obj'].Shape.BoundBox
        x_list.extend([bbox.XMin, bbox.XMax])
        y_list.extend([bbox.YMin, bbox.YMax])
        z_list.extend([bbox.ZMin, bbox.ZMax])
    xvals = min(x_list), max(x_list)
    yvals = min(y_list), max(y_list)
    zvals = min(z_list), max(z_list)
    return xvals, yvals, zvals


def get_joint_info():
    """
    Returns a dictionary (joint_info) containing the joint information
    specified by the JointsSpreadsheet. 
    """
    joint_sheet = App.ActiveDocument.findObjects(Label='JointSpreadsheet')[0]
    col_to_addr = get_nonempty_addr_by_col(joint_sheet)

    joint_info = {}
    for a_addr in col_to_addr['A']:

        index = get_cell_row(a_addr)
        a_value = joint_sheet.get(a_addr)
        a_cell_range = get_cell_data_range(a_addr, col_to_addr)

        child_index = 0 
        joint_info[a_value] = {'parent'   : {}, 'children' : []}

        for b_addr in filter_by_row_range(col_to_addr['B'], *a_cell_range):
            b_value = joint_sheet.get(b_addr)
            b_cell_range = get_cell_data_range(b_addr, col_to_addr)

            for c_addr in filter_by_row_range(col_to_addr['C'], *b_cell_range):
                c_value = joint_sheet.get(c_addr)
                row = get_cell_row(c_addr)
                d_value = joint_sheet.get(f'D{row}')
                if b_value.lower() == 'parent':
                    joint_info[a_value]['parent'][c_value] = d_value
                elif b_value.lower() == 'child':
                    try:
                        joint_info[a_value]['children'][child_index][c_value] = d_value
                    except IndexError:
                        joint_info[a_value]['children'].append({c_value: d_value})
            if b_value.lower() == 'child':
                child_index += 1

    for k,v in joint_info.items():
        fc_print(f'{k}, {v}')


def filter_by_row_range(addr_list, min_row, max_row):
    """
    Filter addr_list by 
    """
    filt_addr_list = []
    for addr in addr_list:
        row = get_cell_row(addr)
        if row >= min_row and row <= max_row:
            filt_addr_list.append(addr)
    return filt_addr_list


def get_cell_data_range(addr, col_to_addr):
    """
    Returns the data range to 

    """
    col = get_cell_col(addr)
    if addr not in col_to_addr[col]:
        # Cell is not in col_to_addr so it is empty and had no data range.
        return None
    data_range_start = get_cell_row(addr) + 1
    min_row, max_row = get_min_and_max_row(col_to_addr)
    addr_pos = col_to_addr[col].index(addr)
    next_pos = addr_pos + 1 
    if next_pos < len(col_to_addr[col]):
        data_range_end = get_cell_row(col_to_addr[col][next_pos]) - 1
    else:
        data_range_end = max_row
    return data_range_start, data_range_end
    

def get_row_list(col_to_addr):
    """
    Returns list of row indices for all addresses in col_to_addr. 
    """
    min_row, max_row = get_min_and_max_row(col_to_addr)
    row_list = list(range(min_row, max_row))
    return row_list


def get_row_list(col_to_addr, col=None):
    """
    Get the list of row indices for all addresses in col_to_addr. Over all
    indices col=None, or over specific column.
    """
    if col is None:
        col_list = [k for k in col_to_addr]
    else:
        col_list = [col]
    row_list = []
    for col in col_list:
            row_list.extend(list(map(get_cell_row, col_to_addr[col])))
    return row_list


def get_col_list(col_to_addr):
    """
    Return lists column letters found in col_to_addr.
    """
    return [k for k in col_to_addr]


def get_min_and_max_row(col_to_addr, col=None):
    """
    Get the minimum and maximum rows for all addresss in col_to_addr (col=None)
    or for a specific column (col=val).
    """
    row_list = get_row_list(col_to_addr, col=col)
    min_row = min(row_list) 
    max_row = max(row_list)
    return min_row, max_row

def get_cell_col(addr):
    """
    Returns the col of the cell given the cell's address string
    """
    return re.search(r'^[A-Z]*', addr)[0]


def get_cell_row(addr):
    """
    Returns the row of the cell given the cell's address string.
    """
    return int(re.search(r'\d*$', addr)[0])


def get_nonempty_addr_by_col(joint_sheet):
    """
    Returns an OrderedDict which gives a list of the nonempty sheet
    cells for each column (A, B, C, D, etc. ) in the sheet. 
    """

    # Get xml element tree containing sheet content remove  addresses
    elem_tree = ET.fromstring(joint_sheet.cells.Content)

    # Get list of addresses for all nonempty cells
    all_addr = []
    for addr in [c.attrib['address'] for c in elem_tree.findall('Cell')]: 
        try:
            joint_sheet.get(addr)
            empty = False 
        except ValueError:
            empty = True 
        if not empty:
            all_addr.append(addr)

    # Get dictionary which maps column letters to list of nonempty cells
    # in that column. 
    col_to_addr = collections.OrderedDict()
    for col in list(string.ascii_uppercase):
        r = re.compile(fr'^{col}\d*$')
        match_list = list(filter(r.match, all_addr))
        if match_list:
            col_to_addr[col] = match_list
    return col_to_addr


def fc_print(msg='', end='\n'):
    """
    A less verbose print function
    """
    FreeCAD.Console.PrintMessage(f'{msg}{end}')



# -----------------------------------------------------------------------------

fc_print()
msg = 'Running A2PlusAssemblyToMujoco'
fc_print(msg)

if 0:
    # Get info required for saving files
    save_info = get_save_info()
    
    # Get list of part objects in assembly and extract information
    part_info = get_part_info()
    
    if 0:
        fc_print(part_info)
    
    # Create mesh files for all parts in the assembly
    if 0:
        create_mesh_files(part_info, save_info)
    
    if 0:
        create_mujoco_xml_file(part_info, save_info)

get_joint_info()




