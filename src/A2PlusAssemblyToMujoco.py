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

DEFAULT_COMPILER_ATTRIB = {
        'coordinate' : 'global'
        }

OPTION_ATTRIB = {
        'gravity'  : '0 0 -1',
        'timestep' : '0.005',
        }

FLOOR_ATTRIB = { 
        'name'     : 'floor', 
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
        'texuniform'  : 'false',  
        'reflectance' : '.2',
        }

LIGHT_ATTRIB = { 
        'name'     : 'spotlight', 
        'mode'     : 'targetbodycom', 
        'diffuse'  : '0.8 0.8 0.8',  
        'specular' : '0.2 0.2 0.2',  
        }

def get_part_info():
    """
    Extracts part information, e.g., postion, rotation, source file.
    """
    app_doc = App.ActiveDocument
    part_info = {}
    for part in app_doc.findObjects(Type='Part::FeaturePython'):
        _, src_file = os.path.split(part.sourceFile)
        part_info[part.Label] = {'part_obj': part, 'src_file': src_file}
    return part_info


def get_file_info():
    active_doc_dir, active_doc_file = os.path.split(App.ActiveDocument.FileName)
    save_dir = select_save_dir_dialog()
    mesh_dir = os.path.join(save_dir, MESH_FILE_DIR)
    file_info = {
            'active_doc_dir'  : active_doc_dir, 
            'active_doc_file' : active_doc_file, 
            'save_dir'        : save_dir,
            'mesh_dir'        : mesh_dir,
            }
    return file_info


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


def create_mesh_files(part_info, file_info):
    """
    Creates an stl file for each part in the part_info and saves it to the
    sub-directory MESH_FILE_DIR of the saveto_dir in the file_info. 
    """
    mesh_dir = file_info['mesh_dir']
    os.makedirs(mesh_dir, exist_ok=True)

    msg = f'saving mesh files to: {mesh_dir}'
    fc_print(msg)

    for item, data in part_info.items():
        part_obj = data['part_obj']
        src_file = data['src_file']
        src_file_fullpath = get_src_fullpath(src_file, file_info)
        base_name = get_base_name(src_file)
        mesh_file = os.path.join(mesh_dir, get_mesh_file(base_name))
        fc_print(f'saving:  {mesh_file}')

        # Open document and save .stl file
        FreeCAD.openDocument(src_file_fullpath)
        App.setActiveDocument(base_name)
        doc = App.getDocument(base_name)
        last_feature_obj = doc.findObjects(Type="PartDesign::Feature")[-1]
        Mesh.export([last_feature_obj], mesh_file)
        App.closeDocument(base_name)


def create_mujoco_xml_file(part_info, file_info, mujoco_info):
    """
    Creates the mujoco xml file.
    """

    # Create element tree  
    root_elem = ET.Element('mujoco')
    compiler_attrib = dict(DEFAULT_COMPILER_ATTRIB)
    try:
        user_compiler_attrib = mujoco_info['compiler']
    except KeyError:
        pass
    else:
        for k,v in user_compiler_attrib.items():
            compiler_attrib[k] = convert_value_to_mujoco_xml(v)
    ET.SubElement(root_elem, 'compiler', attrib=compiler_attrib)

    add_option(root_elem, part_info, mujoco_info)
    add_assets(root_elem, part_info, mujoco_info)
    add_bodies(root_elem, part_info, file_info, mujoco_info)
    add_equalities(root_elem, part_info, file_info, mujoco_info)
    add_actuators(root_elem, part_info, mujoco_info)

    # Save mujoco model to pretty printed xml file
    xml_str = ET.tostring(root_elem)
    xml_str = xml.dom.minidom.parseString(xml_str).toprettyxml(indent='  ')
    save_dir = file_info['save_dir']
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
        base_name = get_base_name(data['src_file'])
        mesh_file = os.path.join('.', MESH_FILE_DIR, get_mesh_file(base_name))
        mesh_attrib = {'file' : mesh_file}
        ET.SubElement(asset_elem, 'mesh', attrib=mesh_attrib)

    # Add material elements for colors 
    color_list = get_color_list(part_info)
    for index, color in enumerate(color_list):
        color_name = f'color_{index}'
        color_vals = ' '.join([f'{val:1.2f}' for val in color])
        color_attrib = {'name': color_name, 'rgba': color_vals} 
        ET.SubElement(asset_elem, 'material', attrib=color_attrib)


    # Add texture and material elements for grid
    ET.SubElement(asset_elem, 'texture', attrib=GRID_TEXTURE_ATTRIB)
    ET.SubElement(asset_elem, 'material', attrib=GRID_MATERIAL_ATTRIB)


def add_bodies(root_elem, part_info, file_info, mujoco_info):
    """
    Adds the top level worldbody element and all subelements to the element
    tree.
    """

    root_mujoco_info = mujoco_info['worldbody']['body_tree']

    # Add worldbody element
    worldbody_elem = ET.SubElement(root_elem, 'worldbody')

    # Get bounding box information 
    xvals, yvals, zvals = get_xyz_extent(part_info)
    xmin, xmax = xvals
    ymin, ymax = yvals
    zmin, zmax = zvals

    # Add floor
    floor_dim = 10*max([xmax, ymax, zmax])
    floor_attrib = dict(FLOOR_ATTRIB)
    floor_attrib['size'] = f'{floor_dim} {floor_dim} 0.05'
    ET.SubElement(worldbody_elem, 'geom', attrib=floor_attrib)

    # Add light
    xpos = 1.5*xmax
    ypos = 1.5*ymax
    zpos = 1.5*zmax
    cutoff = 2*max([xmax, ymax, zmax])
    light_attrib = dict(LIGHT_ATTRIB)
    light_attrib['pos'] = f'{xpos} {ypos} {zpos}'
    light_attrib['cutoff'] = f'{cutoff}' 
    light_attrib['target'] = root_mujoco_info['label']
    ET.SubElement(worldbody_elem, 'light', attrib=light_attrib)

    # Get placement of root object in worldbody
    root_label = root_mujoco_info['label']
    root_src_file = part_info[root_label]['src_file']
    root_base_name = get_base_name(root_src_file)
    root_src_file = get_src_fullpath(root_src_file, file_info)
    try:
        root_point = root_mujoco_info['joint']['position']
    except KeyError:
        root_base_vector = FreeCAD.Vector(0.0, 0.0, 0.0)
    else:
        root_base_vector = get_placement_base_vector(root_src_file, root_point)

    label_to_color_name = get_label_to_color_name(part_info)

    # Begin inner function -----------------------------------------------------
    def add_body_to_tree(parent_elem, parent_mujoco_info, body_mujoco_info):
        """
        Adds the current, specified by body_mujoco_info, to the the parent 
        element. 
        """

        # Get parent information
        if parent_mujoco_info:
            parent_label = parent_mujoco_info['label']
            parent_src_file = part_info[parent_label]['src_file']
            parent_src_file = get_src_fullpath(parent_src_file, file_info)
            parent_obj = part_info[parent_label]['part_obj']
            parent_rot = parent_obj.Placement.Rotation
        else:
            parent_label = None
            parent_src_file = None
            parent_scr_file = None
            parent_obj = None
            parent_rot = None

        # Extract body information
        body_label = body_mujoco_info['label']
        body_part_info = part_info[body_label]
        body_src_file = body_part_info['src_file']
        body_placement = body_part_info['part_obj'].Placement
        body_pos_vector = body_placement.Base
        body_base_name = get_base_name(body_src_file)
        body_color_name = label_to_color_name[body_label]
    
        # Get position vector and str
        pos_vector = body_pos_vector - root_base_vector
        body_pos_str = vector_to_str(pos_vector)

        # Get orientation
        body_quat = convert_quat_to_mujoco(body_placement.Rotation.Q) 
        body_quat_str = vector_to_str(body_quat)

        # Create element for current body
        body_attrib = {
                'name' : body_label,
                'pos'  : body_pos_str, 
                'quat' : body_quat_str, 
                }
        body_elem = ET.SubElement(parent_elem, 'body', attrib=body_attrib)
    
        # Add geom sub-element
        body_mesh_name = f'{body_label}_mesh' 
        geom_attrib = {
                'name'     : body_mesh_name,
                'type'     : 'mesh', 
                'mesh'     : body_base_name, 
                'material' : body_color_name, 
                'pos'      : body_pos_str, 
                'quat'     : body_quat_str, 
                }
        ET.SubElement(body_elem, 'geom', attrib=geom_attrib)
    
        # Add joint sub-element 
        if 'joint' in body_mujoco_info:
            body_joint_name = f'{body_label}_joint'
            body_joint_type = body_mujoco_info['joint']['type']
            body_joint_attrib = {'name' : body_joint_name} 
            if body_joint_type == 'freejoint':
                ET.SubElement(body_elem, 'freejoint', attrib=body_joint_attrib)
            else:
                body_joint_attrib.update({
                        'name' : body_joint_name, 
                        'type' : body_joint_type, 
                        'pos'  : body_pos_str,
                    })
                try:
                    body_joint_parameters = body_mujoco_info['joint']['parameters']
                except KeyError:
                    pass
                else:
                    for k,v in body_joint_parameters.items(): 
                        body_joint_attrib[k] = convert_value_to_mujoco_xml(v)
                        if k == 'axis':
                            axis_vector = get_datum_line_vector(parent_src_file, v)
                            axis_vector = parent_rot.multVec(axis_vector)
                            body_joint_attrib['axis'] = vector_to_str(axis_vector)
                        else:
                            body_joint_attrib[k] = convert_value_to_mujoco_xml(v)
                ET.SubElement(body_elem, 'joint', attrib=body_joint_attrib)

        # If the body has children recurse into them
        if 'children' in body_mujoco_info:
            for child_mujoco_info in body_mujoco_info['children']:
                add_body_to_tree(body_elem, body_mujoco_info, child_mujoco_info)
    # End inner function -------------------------------------------------------

    add_body_to_tree(worldbody_elem, {}, root_mujoco_info)
    

def add_equalities(root_elem, part_info, file_info, mujoco_info):
    if not 'equality' in mujoco_info:
        return
    equality_elem = ET.SubElement(root_elem, 'equality')
    for equality_info in mujoco_info['equality']:
        equality_tag = equality_info['type']
        equality_attrib = {}
        try:
            param_info = equality_info['parameters']
        except KeyError:
            pass
        else:
            for k, v in param_info.items():
                if k == 'anchor':
                    body2_label = param_info['body2']
                    body2_part_obj = part_info[body2_label]['part_obj']
                    body2_src_file = part_info[body2_label]['src_file']
                    body2_src_file = get_src_fullpath(body2_src_file, file_info)
                    anchor_vector = get_placement_base_vector(body2_src_file, v)
                    body2_vector = body2_part_obj.Placement.Base
                    body2_rotation = body2_part_obj.Placement.Rotation
                    anchor_vector = body2_rotation.multVec(anchor_vector)
                    anchor_vector = anchor_vector + body2_vector
                    equality_attrib[k] = vector_to_str(anchor_vector)
                else:
                    equality_attrib[k] = convert_value_to_mujoco_xml(v)
        ET.SubElement(equality_elem, equality_tag, attrib=equality_attrib )


def add_actuators(root_elem, part_info, mujoco_info):
    if not 'actuator' in mujoco_info:
        return
    actuator_elem = ET.SubElement(root_elem, 'actuator')
    for actuator_info in mujoco_info['actuator']:
        actuator_tag = actuator_info['type']
        actuator_attrib = {}
        try:
            param_info = actuator_info['parameters']
        except KeyError:
            pass
        else:
            for k, v in param_info.items():
                actuator_attrib[k] = convert_value_to_mujoco_xml(v)
        ET.SubElement(actuator_elem, actuator_tag, attrib=actuator_attrib )


def convert_value_to_mujoco_xml(value):
    converted_value = value
    if value in (True, False):
        converted_value = str(value).lower()
    elif type(value) in (list, tuple):
        converted_value = ' '.join([str(x) for x in value])
    else:
        converted_value = str(value)
    return converted_value


def get_placement_base_vector(part_file, obj_label):
    """
    Get the vector specifying the placement base of an object in a a part file.
    """
    _, file_name = os.path.split(part_file)
    base_name, _ = os.path.splitext(file_name)
    FreeCAD.openDocument(part_file)
    App.setActiveDocument(base_name)
    doc = App.getDocument(base_name)
    obj = doc.findObjects(Label=obj_label)[0]
    base_vector = obj.Placement.Base
    App.closeDocument(base_name)
    return base_vector


def get_placement_rotation(part_file, obj_label):
    """
    Get the rotataion specifying the object orientation of an object given a 
    part file and an object label. 
    """
    _, file_name = os.path.split(part_file)
    base_name, _ = os.path.splitext(file_name)
    FreeCAD.openDocument(part_file)
    App.setActiveDocument(base_name)
    doc = App.getDocument(base_name)
    obj = doc.findObjects(Label=obj_label)[0]
    rotation = obj.Placement.Rotation
    App.closeDocument(base_name)
    return rotation


def get_datum_line_vector(part_file, axis_label):
    """
    Get the vector of a datum linegiven the part file and the label of the axis
    object.
    """
    rotation = get_placement_rotation(part_file, axis_label)
    axis_vector = rotation.multVec(FreeCAD.Vector(0.0, 0.0, 1.0))
    return axis_vector


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
    color_list = get_color_list(part_info)
    label_to_color_name = {}
    for k, v in part_info.items():
        color = get_part_color(v['part_obj'])
        color_index = color_list.index(color)
        color_name = f'color_{color_index}'
        label_to_color_name[k] = color_name
    return label_to_color_name


def get_color_list(part_info):
    """
    Get list of unique colors used in part assembly
    """
    color_set = {get_part_color(v['part_obj']) for k, v in part_info.items()}
    return list(color_set)


def get_part_color(part_obj):
    """
    Get color of part in assembly
    """
    gui_doc = FreeCADGui.getDocument(App.ActiveDocument.Name)
    part_color = invert_color_alpha(gui_doc.getObject(part_obj.Name).ShapeColor)
    return part_color


def invert_color_alpha(color):
    """
    Invert alpha range in 4-tuple color 0 -> 1 and 1 -> 0. 
    """
    color_list = list(color)
    color_list[-1] = 1.0 - color_list[-1]
    return tuple(color_list)


def vector_to_str(vector):
    """
    Converts a vector to a string representation of the vector
    """
    return ' '.join([str(x) for x in vector])


def convert_quat_to_mujoco(q):
    """
    Convert FreeCAD quaternion to mujoco's convention.
    """
    return (q[3], q[0], q[1], q[2])


def load_mujoco_yaml_file(file_info):
    """
    Loads extra data required for creating mujoco xml from the mujoco yaml
    file. 
    """
    mujoco_file = App.ActiveDocument.Spreadsheet.get('MujocoFile')
    mujoco_file = os.path.join(file_info['active_doc_dir'], mujoco_file)
    with open(mujoco_file, 'r') as f:
        mujoco_data = yaml.safe_load(f)
    return mujoco_data


def get_base_name(src_file):
    """
    Get base name of file - filename without the file extension.
    """
    base_name, _ = os.path.splitext(src_file)
    return base_name


def get_src_fullpath(src_file, file_info):
    """
    Get fullpath of source file.
    """
    return os.path.join(file_info['active_doc_dir'], src_file)


def fc_print(msg='', end='\n'):
    """
    A less verbose print function
    """
    FreeCAD.Console.PrintMessage(f'{msg}{end}')



# -----------------------------------------------------------------------------

fc_print()
msg = 'Running A2PlusAssemblyToMujoco'
fc_print(msg)

file_info_tmp = get_file_info()
part_info = get_part_info()
mujoco_info = load_mujoco_yaml_file(file_info_tmp)

#fc_print(file_info)
#fc_print(part_info)
#fc_print(mujoco_info)

# Create mesh files for all parts in the assembly
if 1:
    create_mesh_files(part_info, file_info_tmp)

create_mujoco_xml_file(part_info, file_info_tmp, mujoco_info)

