"""
Install the FreeCAD macros, to install_dir, by creating symbolic links
"""
import os
import sys

home_dir = os.environ['HOME']
install_dir = os.path.join(home_dir, '.local', 'share', 'FreeCAD', 'Macro')
source_dir = os.path.join(os.curdir, 'src')
macro_ext = 'FCMacro'

print()
print('make symbolic links to FreeCAD macros')
print()
print(f'  source dir:  {source_dir}')
print(f'  install dir: {install_dir}')
print()

macro_list = os.listdir(source_dir)

for filename in os.listdir(source_dir):
    basename, extname = os.path.splitext(filename)
    if extname != '.py':
        continue
    src_pathname =  os.path.abspath(os.path.join(source_dir, filename))
    dst_pathname = os.path.join(install_dir, f'{basename}.{macro_ext}')
    print(f'  {src_pathname} -> {dst_pathname}')
    if os.path.exists(dst_pathname) or os.path.islink(dst_pathname):
        os.unlink(dst_pathname)
    os.symlink(src_pathname, dst_pathname)
print()
