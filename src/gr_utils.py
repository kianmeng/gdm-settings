''' Utilities (functions) for GResource files of GNOME Shell themes'''

import os
import logging
from . import env
from . import utils

ThemesDir                = env.HOST_DATA_DIRS[0]
CustomThemeIdentity      = 'custom-theme'
GdmUsername              = 'gdm'
ShellGresourceFile       = None
ShellGresourceAutoBackup = None
CustomGresourceFile      = None
UbuntuGdmGresourceFile   = None

for data_dir in env.HOST_DATA_DIRS:
    file = os.path.join (data_dir,  'gnome-shell', 'gnome-shell-theme.gresource')
    if os.path.isfile (env.HOST_ROOT + file):
        ShellGresourceFile       = file
        ShellGresourceAutoBackup = ShellGresourceFile + ".default"
        CustomGresourceFile      = ShellGresourceFile + ".gdm_settings"
        break

if 'ubuntu' in [env.OS_ID] + env.OS_ID_LIKE.split():
    from .utils import version
    if version(env.OS_VERSION_ID) >= version('21.10'):
        UbuntuGdmGresourceFile = '/usr/share/gnome-shell/gdm-theme.gresource'
    else:
        UbuntuGdmGresourceFile = '/usr/share/gnome-shell/gdm3-theme.gresource'
elif 'debian' in [env.OS_ID] + env.OS_ID_LIKE.split():
    GdmUsername = 'Debian-gdm'


def is_unmodified(gresourceFile:str):
    """checks if the provided file is a GResource file of the default theme"""

    from .utils import getstdout

    if os.path.exists(gresourceFile):
        if getstdout(["gresource", "list", gresourceFile, "/org/gnome/shell/theme/gnome-shell.css"]):
            if not getstdout(f"gresource list {gresourceFile} /org/gnome/shell/theme/{CustomThemeIdentity}"):
                return True
    return False

def get_default() -> str:
    """get full path to the unmodified GResource file of the default theme (if the file exists)"""

    for file in ShellGresourceFile, ShellGresourceAutoBackup:
       if is_unmodified(env.HOST_ROOT + file):
           return file

def extract_default_theme(destination:str, /):
    '''Extract default GNOME Shell theme'''

    from os import makedirs
    from .utils import getstdout

    if os.path.exists(destination):
        from shutil import rmtree
        rmtree(destination)

    destination_shell_dir = os.path.join(destination, 'gnome-shell')
    gresource_file = get_default()
    resource_list = getstdout(["gresource", "list", env.HOST_ROOT + gresource_file]).decode().splitlines()

    if not gresource_file:
        raise FileNotFoundError('No unmodified GResource file of the default shell theme was found')

    for resource in resource_list:
        filename = resource.removeprefix("/org/gnome/shell/theme/")
        filepath = os.path.join(destination_shell_dir, filename)
        content  = getstdout(["gresource", "extract", env.HOST_ROOT + gresource_file, resource])

        makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "wb") as opened_file:
            opened_file.write(content)

class BackgroundImageNotFoundError (FileNotFoundError): pass

def compile(shellDir:str, overlay_mode:str, additional_css:str, background_image:str=''):
    """Compile a theme into a GResource file for its use as a GDM theme"""

    from os import remove
    from shutil import move, copy, copytree, rmtree

    temp_gresource_file = os.path.join(env.TEMP_DIR, 'gnome-shell-theme.gresource')
    temp_gresource_xml = f'{temp_gresource_file}.xml'
    temp_theme_dir = os.path.join(env.TEMP_DIR, 'temp-theme')
    temp_shell_dir = os.path.join(temp_theme_dir, 'gnome-shell')

    # Remove temporary directory if already exists
    if os.path.exists(temp_theme_dir):
        rmtree(temp_theme_dir)

    # Remove temporary file if already exists
    if os.path.exists(temp_gresource_file):
        remove(temp_gresource_file)

    if not shellDir:
        extract_default_theme(temp_theme_dir)
    else:
        if overlay_mode == 'nothing':
            copytree(shellDir, temp_shell_dir, dirs_exist_ok=True)
        elif overlay_mode == 'resources':
            extract_default_theme(temp_theme_dir)
            copytree(shellDir, temp_shell_dir, dirs_exist_ok=True)
        elif overlay_mode == 'everything':
            extract_default_theme(temp_theme_dir)
            shell_css_file = os.path.join(temp_shell_dir, 'gnome-shell.css')
            shell_css_file_bak = shell_css_file+'.bak'
            move(shell_css_file, shell_css_file_bak)
            copytree(shellDir, temp_shell_dir, dirs_exist_ok=True)
            with open(shell_css_file_bak, 'a') as default_css:
                with open(shell_css_file, 'r') as theme_css:
                    default_css.write('\n')
                    default_css.write(theme_css.read())
            move(shell_css_file_bak, shell_css_file)
        else:
            raise ValueError("value of 'shell-theme-overlay' key is not one of"
                             " ['nothing', 'resources', 'everything']")

    # Inject custom-theme identity
    open(os.path.join(temp_shell_dir, CustomThemeIdentity), 'w').close()

    # Background Image
    if background_image:
        if os.path.isfile(background_image):
            copy(background_image, os.path.join(temp_shell_dir, 'background'))
        else:
            raise BackgroundImageNotFoundError(2, 'No such file', background_image)

    # Additional CSS
    with open(f"{temp_shell_dir}/gnome-shell.css", "a") as shell_css:
        print(additional_css, file=shell_css)

    # Copy gnome-shell.css to gdm.css and gdm3.css
    copy(f"{temp_shell_dir}/gnome-shell.css", f"{temp_shell_dir}/gdm.css")
    copy(f"{temp_shell_dir}/gnome-shell.css", f"{temp_shell_dir}/gdm3.css")

    with open(temp_gresource_xml, 'w') as GresourceXml:
        print('<?xml version="1.0" encoding="UTF-8"?>',
              '<gresources>',
              ' <gresource prefix="/org/gnome/shell/theme">',
            *('  <file>'+file+'</file>' for file in utils.listdir_recursive(temp_shell_dir)),
              ' </gresource>',
              '</gresources>',

              sep='\n',
              file=GresourceXml,
             )

    # Compile Theme
    from subprocess import run
    run(['glib-compile-resources',
         '--sourcedir', temp_shell_dir,
         '--target', temp_gresource_file,
         temp_gresource_xml,
       ])

    # Return path to the generated GResource file
    return  temp_gresource_file
