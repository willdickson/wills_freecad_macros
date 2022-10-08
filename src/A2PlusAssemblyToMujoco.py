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
import xml.etree.ElementTree as ET

__title__    = 'A2PlusAssemblyToMujoco'
__author__   = 'Will Dickson'
__version__  = '0.1.01'
__date__     = '2022-09-07'
__Comment__  = 'Convert machine assemblies made in A2Plus to mujoco xml'
__Status__   = 'unstable'
__Requires__ = 'FreeCAD 0.19'

MESH_FILE_DIR = 'mesh_files'

def get_part_objs():
    """
    Returns a list of all parts in the assembly document's tree
    """
    doc = App.ActiveDocument
    part_obj_list = [p for p in doc.findObjects() if 'Part:' in p.TypeId]
    return part_obj_list


def get_part_info(part_obj_list):
    """
    Extracts part information, e.g., postion, rotation, source file.
    """
    part_info_dict = {}
    for part in part_obj_list:
        p = part.Placement.Base
        q = part.Placement.Rotation
        axis = part.Placement.Rotation.Axis
        angle = part.Placement.Rotation.Angle
        src_file = part.sourceFile
        part_info_dict[part.Label] = {
                'pos'      : p, 
                'quat'     : q, 
                'axis'     : axis,
                'angle'    : angle,
                'src_file' : src_file
                }
        #print(part.Label)
        #for k,v in part_info_dict[part.Label].items():
        #    print(f'{k}: {v}')
        #print()
    return part_info_dict


def create_mesh_files(part_info_dict):
    """
    Creates an stl file for each part object.

    Location is where you opened freecad ... 
    """
    mesh_dir = os.path.join(os.curdir, MESH_FILE_DIR)
    os.makedirs(mesh_dir, exist_ok=True)
    print(mesh_dir)


# -----------------------------------------------------------------------------

FreeCAD.Console.PrintMessage(f'Running A2PlusAssemblyToMujoco\n') 

part_obj_list = get_part_objs()
part_info_dict = get_part_info(part_obj_list)
create_mesh_files(part_info_dict)


