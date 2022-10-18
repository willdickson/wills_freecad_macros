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
import yaml
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
        base_name, _ = os.path.splitext(src_file)
        shape_color = gui_doc.getObject(part.Name).ShapeColor
        part_info[part.Label] = {
                'pos'        : p, 
                'quat'       : q, 
                'axis'       : axis,
                'angle'      : angle,
                'src_file'   : src_file,
                'base_name'  : base_name, 
                'part_obj'   : part,
                'color'      : shape_color,
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


def get_mesh_file(base_name):
    mesh_file = f'{base_name}.stl'
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
        part_file = os.path.join(save_info['active_doc_dir'], data['src_file'])
        base_name = data['base_name']
        part_obj = data['part_obj']
        mesh_file = os.path.join(mesh_dir, get_mesh_file(base_name))
        fc_print(f'saving:  {mesh_file}')

        # Open document and save .stl file
        FreeCAD.openDocument(part_file)
        App.setActiveDocument(base_name)
        doc = App.getDocument(base_name)
        last_feature_obj = doc.findObjects(Type="PartDesign::Feature")[-1]
        Mesh.export([last_feature_obj], mesh_file)
        App.closeDocument(base_name)


def create_mujoco_xml_file(part_info, save_info, mujoco_info):
    """
    Creates the mujoco xml file.
    """

    # Create element tree  
    root_elem = ET.Element('mujoco')
    ET.SubElement(root_elem, 'compiler', attrib=COMPILER_ATTRIB)

    add_option(root_elem, part_info, mujoco_info)
    add_assets(root_elem, part_info, mujoco_info)
    add_bodies(root_elem, part_info, mujoco_info)
    add_equalities(root_elem, part_info, mujoco_info)
    add_actuators(root_elem, part_info, mujoco_info)

    # Save mujoco model to pretty printed xml file
    xml_str = ET.tostring(root_elem)
    xml_str = xml.dom.minidom.parseString(xml_str).toprettyxml(indent='  ')
    save_dir = save_info['save_dir']
    mujoco_xml_file = os.path.join(save_dir, MUJOCO_MODEL_FILE)
    with open(mujoco_xml_file, 'w') as f:
        f.write(xml_str)

def add_option(root_elem, part_info, mujoco_info):
    option_attrib = dict(OPTION_ATTRIB)
    for k,v in mujoco_info['option'].items():
        if type(v) == list:
            option_attrib[k] = ' '.join([str(item) for item in v])
        else:
            option_attrib[k] = str(v) 
    ET.SubElement(root_elem, 'option', attrib=option_attrib)


def add_assets(root_elem, part_info, mujoco_info):
    """
    Adds the assets element and all sub elements to the element tree
    """
    asset_elem = ET.SubElement(root_elem, 'asset') 
    for item, data in part_info.items():
        base_name = data['base_name']
        mesh_file = os.path.join('.', MESH_FILE_DIR, get_mesh_file(base_name))
        mesh_attrib = {'file' : mesh_file}
        ET.SubElement(asset_elem, 'mesh', attrib=mesh_attrib)

    # Add material elements for colors 
    color_list = list({data['color'] for item, data in part_info.items()})
    for index, color in enumerate(color_list):
        color_name = f'color_{index}'
        color_vals = ' '.join([f'{val:1.2f}' for val in color])
        color_attrib = {'name': color_name, 'rgba': color_vals} 
        ET.SubElement(asset_elem, 'material', attrib=color_attrib)


    # Add texture and material elements for grid
    ET.SubElement(asset_elem, 'texture', attrib=GRID_TEXTURE_ATTRIB)
    ET.SubElement(asset_elem, 'material', attrib=GRID_MATERIAL_ATTRIB)


def add_bodies(root_elem, part_info, mujoco_info):
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
    worldbody_elem = ET.SubElement(worldbody_elem, 'light', attrib=LIGHT_ATTRIB)

    root_mujoco_info = mujoco_info['worldbody']['body_tree']


    # Develop - example of extracting placement vector from part
    # -----------------------------------------------------------
    root_label = root_mujoco_info['label']
    root_src_file = part_info[root_label]['src_file']
    root_part_file = os.path.join(save_info['active_doc_dir'], root_src_file)
    root_base_name = part_info[root_label]['base_name']
    root_world_point = root_mujoco_info['joint']['position']

    FreeCAD.openDocument(root_part_file)
    App.setActiveDocument(root_base_name)
    doc = App.getDocument(root_base_name)
    root_point_obj = doc.findObjects(Label=root_world_point)[0]
    root_point_vector = point_obj.Placement.Base
    App.closeDocument(root_base_name)
    # -----------------------------------------------------------

    label_to_color_name = get_label_to_color_name(part_info)

    # Begin inner function -----------------------------------------------------

    def add_body_to_tree(parent_elem, body_mujoco_info):
        """
        Adds the current, specified by body_mujoco_info, to the the parent 
        element. 
        """
        label = body_mujoco_info['label']
        body_part_info = part_info[label]
    
        # Create element for current body
        body_attrib = {
                'name' : label,
                'pos'  : ' '.join([str(x) for x in body_part_info['pos']]),  
                }
        body_elem = ET.SubElement(parent_elem, 'body', attrib=body_attrib)
    
        # Add geom sub-element
        geom_attrib = {
                'name'     : f'{label}_mesh', 
                'type'     : 'mesh', 
                'mesh'     : body_part_info['base_name'], 
                'material' : label_to_color_name[label], 
                }
        ET.SubElement(body_elem, 'geom', attrib=geom_attrib)
    
        # Add joint sub-element 
        if body_mujoco_info['joint']['type'] == 'freejoint':
            joint_attrib = {'name' : f'{label}_joint'}
            ET.SubElement(body_elem, 'freejoint', attrib=joint_attrib)
        else:
            joint_attrib = {
                    'name' : f'{label}_joint',
                    'type' : body_mujoco_info['joint']['type'],
                    }
            ET.SubElement(body_elem, 'joint', attrib=joint_attrib)
    
        # If the body has children recurse into them
        if 'children' in body_mujoco_info:
            for child_mujoco_info in body_mujoco_info['children']:
                add_body_to_tree(body_elem, child_mujoco_info)

    # End inner function -------------------------------------------------------


    add_body_to_tree(worldbody_elem, root_mujoco_info)
    


def add_equalities(root_elem, part_info, mujoco_info):
    pass


def add_actuators(root_elem, part_info, mujoco_info):
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


def get_label_to_color_name(part_info):
    """ 
    Creates mapping from part label to color names
    """
    color_list = list({data['color'] for item, data in part_info.items()})
    label_to_color_name = {}
    for item, data in part_info.items():
        index = color_list.index(data['color'])
        color_name = f'color_{index}'
        label_to_color_name[item] = color_name
    return label_to_color_name


def load_mujoco_yaml_file():
    """
    Loads extra data required for creating mujoco xml from the mujoco yaml
    file. 
    """
    mujoco_file = App.ActiveDocument.Spreadsheet.get('MujocoFile')
    with open(mujoco_file, 'r') as f:
        mujoco_data = yaml.safe_load(f)
    return mujoco_data


def fc_print(msg='', end='\n'):
    """
    A less verbose print function
    """
    FreeCAD.Console.PrintMessage(f'{msg}{end}')



# -----------------------------------------------------------------------------

fc_print()
msg = 'Running A2PlusAssemblyToMujoco'
fc_print(msg)

save_info = get_save_info()
part_info = get_part_info()
mujoco_info = load_mujoco_yaml_file()

#fc_print(save_info)
#fc_print(part_info)
#fc_print(mujoco_info)

# Create mesh files for all parts in the assembly
if 0:
    create_mesh_files(part_info, save_info)

create_mujoco_xml_file(part_info, save_info, mujoco_info)

