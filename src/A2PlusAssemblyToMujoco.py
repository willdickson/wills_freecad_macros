"""
A2PlusAssemblyToMujoco.py 

Macro to automatically convert an assembly of a mechanical model made
in the A2Plus workbench to a mujoco xml file. 

Notes:
Currently in development.  May require annotating the A2Plus assembly and
or the source files in some fashion to help specify where the joints are
locate, what kind of joints they are etc. 

"""
import os
import string 
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
    msg = f'saving mesh files to: {mesh_dir}\n'
    FreeCAD.Console.PrintMessage(msg)

    for item, data in part_info.items():
        part_file = os.path.join(save_info['active_doc_dir'], data['part_file'])
        part_name = data['part_name']
        part_obj = data['part_obj']
        mesh_file = os.path.join(mesh_dir, get_mesh_file(part_name))
        FreeCAD.Console.PrintMessage(f'saving:  {mesh_file}\n')

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
    add_compiler(root_elem, part_info)
    add_options(root_elem, part_info)
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


def add_compiler(root_elem, part_info):
    """
    Adds the compiler element to the elements tree
    """
    compiler_attrib = {
            'coordinate' : 'global',
            }
    ET.SubElement(root_elem, 'compiler', attrib=compiler_attrib)


def add_options(root_elem, part_info):
    """
    Adds the option element to the element tree
    """

    option_attrib = {
            'gravity'  : '0 0 -1',
            'timestep' : '0.005',
            }
    ET.SubElement(root_elem, 'option', attrib=option_attrib)


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
    grid_texture_attrib = { 
            'name'    : 'grid',  
            'type'    : '2d', 
            'builtin' : 'checker',  
            'width'   : '512',  
            'height'  : '512',  
            'rgb1'    : '0.1 0.2 0.3',  
            'rgb2'    : '0.2 0.3 0.4',
            }
    ET.SubElement(asset_elem, 'texture', attrib=grid_texture_attrib)
    grid_material_attrib = { 
            'name'        : 'grid',  
            'texture'     : 'grid',  
            'texrepeat'   : '10 10',  
            'texuniform'  : 'true',  
            'reflectance' : '.2',
            }
    ET.SubElement(asset_elem, 'material', attrib=grid_material_attrib)


def add_bodies(root_elem, part_info):
    """
    Adds the top level worldbody element and all subelements to the element
    tree.
    """

    # Add worldbody element
    worldbody_elem = ET.SubElement(root_elem, 'worldbody')

    # Add floor
    floor_attrib = { 
            'name'     : 'floor', 
            'size'     : '0 0 .05',  
            'type'     : 'plane',  
            'material' : 'grid',  
            'condim'   : '3', 
            }
    ET.SubElement(worldbody_elem, 'geom', attrib=floor_attrib)

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
    light_attrib = { 
            'name'     : 'spotlight', 
            'mode'     : 'targetbodycom', 
            'target'   : 'base',  
            'diffuse'  : '0.8 0.8 0.8',  
            'specular' : '0.2 0.2 0.2',  
            'pos'      : f'{xpos}, {ypos},{zpos}',
            'cutoff'   : f'{cutoff}', 
            }
    ET.SubElement(worldbody_elem, 'light', attrib=light_attrib)


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

    joints_col_to_addr = get_joints_col_to_addr()
    for col, addr_list in joints_col_to_addr.items():
        if addr_list:
            FreeCAD.Console.PrintMessage(f'{col} {addr_list}\n')


def get_joints_col_to_addr():

    # Get xml element tree containing sheet content remove  addresses
    joints_sheet = App.ActiveDocument.findObjects(Label='JointsSpreadsheet')[0]
    elem_tree = ET.fromstring(joints_sheet.cells.Content)

    # Get list of addresses for all nonempty cells
    all_addr = []
    for addr in [c.attrib['address'] for c in elem_tree.findall('Cell')]: 
        try:
            joints_sheet.get(addr)
            empty = False 
        except ValueError:
            empty = True 
        if not empty:
            all_addr.append(addr)

    # Get dictionary which maps column letters to list of nonempty cells
    # in that column. 
    col_to_addr = {}
    for col in list(string.ascii_uppercase):
        r = re.compile(fr'^{col}\d*$')
        col_to_addr[col] = list(filter(r.match, all_addr))
    return col_to_addr








# -----------------------------------------------------------------------------

FreeCAD.Console.PrintMessage('\n')
msg = 'Running A2PlusAssemblyToMujoco\n'
FreeCAD.Console.PrintMessage(msg)

# Get info required for saving files
save_info = get_save_info()

# Get list of part objects in assembly and extract information
part_info = get_part_info()

if 0:
    FreeCAD.Console.PrintMessage(part_info)

# Create mesh files for all parts in the assembly
if 0:
    create_mesh_files(part_info, save_info)

if 0:
    create_mujoco_xml_file(part_info, save_info)

get_joint_info()




