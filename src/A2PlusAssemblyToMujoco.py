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
import FreeCAD
import xml.dom.minidom
import xml.etree.ElementTree as ET

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
    part_info_dict = {}
    for part in App.ActiveDocument.findObjects('Part::FeaturePython'):
        p = part.Placement.Base
        q = part.Placement.Rotation
        axis = part.Placement.Rotation.Axis
        angle = part.Placement.Rotation.Angle
        _, src_file = os.path.split(part.sourceFile)
        name, _ = os.path.splitext(src_file)
        part_info_dict[part.Label] = {
                'pos'        : p, 
                'quat'       : q, 
                'axis'       : axis,
                'angle'      : angle,
                'part_name'  : name, 
                'part_file'  : src_file,
                'part_obj'   : part,
                }
    return part_info_dict


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


def create_mesh_files(part_info_dict, save_info):
    """
    Creates an stl file for each part in the part_info_dict and saves it to the
    sub-directory MESH_FILE_DIR of the saveto_dir in the save_info. 
    """
    os.makedirs(save_info['mesh_dir'], exist_ok=True)
    msg = f'saving mesh files to: {mesh_dir}\n'
    FreeCAD.Console.PrintMessage(msg)

    for item, data in part_info_dict.items():
        part_file = os.path.join(save_info['active_doc_dir'], data['part_file'])
        part_name = data['part_name']
        part_obj = data['part_obj']
        mesh_dir = save_info['mesh_dir']
        mesh_file = os.path.join(mesh_dir, get_mesh_file(part_name))
        FreeCAD.Console.PrintMessage(f'saving:  {mesh_file}\n')

        # Open document and save .stl file
        FreeCAD.openDocument(part_file)
        App.setActiveDocument(part_name)
        doc = App.getDocument(part_name)
        last_feature_obj = doc.findObjects("PartDesign::Feature")[-1]
        Mesh.export([last_feature_obj], mesh_file)
        App.closeDocument(part_name)


def create_mujoco_xml_file(part_info_dict, save_info):

    # Create root element 
    root_elem = ET.Element('mujoco')

    # Add options
    option_elem_attrib = {
            'gravity'  : '0 0 -1',
            'timestep' : '0.005',
            }
    option_elem = ET.SubElement(root_elem, 'option', attrib=option_elem_attrib)

    # Add assets
    asset_elem = ET.SubElement(root_elem, 'asset') 
    for item, data in part_info_dict.items():
        part_name = data['part_name']
        mesh_file = os.path.join('.', MESH_FILE_DIR, get_mesh_file(part_name))
        mesh_elem_attrib = {'file' : mesh_file}
        mesh_elem = ET.SubElement(asset_elem, 'mesh', attrib=mesh_elem_attrib)

    # Add colors to assests

    # Save mujoco model to pretty printed xml file
    xml_str = ET.tostring(root_elem)
    xml_str = xml.dom.minidom.parseString(xml_str).toprettyxml(indent='  ')
    save_dir = save_info['save_dir']
    mujoco_file = os.path.join(save_dir, MUJOCO_MODEL_FILE)
    with open(mujoco_file, 'w') as f:
        f.write(xml_str)






# -----------------------------------------------------------------------------

FreeCAD.Console.PrintMessage('\n')
msg = 'Running A2PlusAssemblyToMujoco\n'
FreeCAD.Console.PrintMessage(msg)

# Get info required for saving files
save_info = get_save_info()

# Get list of part objects in assembly and extract information
part_info_dict = get_part_info()

# Create mesh files for all parts in the assembly
#create_mesh_files(part_info_dict, save_info)

create_mujoco_xml_file(part_info_dict, save_info)




