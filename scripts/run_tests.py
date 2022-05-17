# <pep8 compliant>
import os
import sys
import zipfile
from pathlib import Path

from scripts.utils import zipdir, parser, remove_folders_matching_pattern, download_stop_motion_obj_addon

print("---------------------------------------- RUN TESTS START ---------------------------------------------")

try:
    import blender_addon_tester as BAT
except Exception as e:
    print(e)
    sys.exit(1)


def main():
    arguments = parser.parse_args()
    # Get addon path

    if arguments.n is None:
        print("ERROR: -n option is None.")
        parser.parse_args(['-h'])

    name = arguments.n

    if arguments.a is None:
        print("ERROR: -a option is None.")
        parser.parse_args(['-h'])

    addon = arguments.a

    # Get blender version(s) to test the addon
    if arguments.b is None:
        print("ERROR: -b option is None.")
        parser.parse_args(['-h'])

    blender_rev = arguments.b

    here = Path(__file__).parent

    try:
        # Cleanup '__pychache__' folders in the 'src' folder
        remove_folders_matching_pattern(os.path.join(os.path.relpath("."), "src"))

        # Download addons on which this addon depends
        smo_path, smo_module_name = download_stop_motion_obj_addon(here.joinpath("../cache").as_posix())
        os.environ["STOP_MOTION_OBJ_PATH"] = smo_path
        os.environ["STOP_MOTION_OBJ_MODULE"] = smo_module_name

        # Zip addon
        if not addon.endswith(".zip"):
            print("Zipping addon - " + name)
            zipf = zipfile.ZipFile(name + ".zip", 'w', zipfile.ZIP_DEFLATED)
            zipdir("./" + name, zipf)
            zipf.close()
            addon = os.path.join(os.path.abspath("."), name + ".zip")

    except Exception as e:
        print(e)
        exit_val = 1

    # Custom configuration
    config = {
        "blender_load_tests_script": here.joinpath("load_pytest.py").as_posix(),
        "coverage": False,
        "tests": here.joinpath("../tests").as_posix(),
        "blender_cache": here.joinpath("../cache").as_posix()
    }

    try:
        # Setup custom blender cache (where the blender versions will be downloaded and extracted)
        # The blender_addon_tester module raises an error when passed as a key in the config dict
        if config.get("blender_cache", None):
            os.environ["BLENDER_CACHE"] = config["blender_cache"]
            config.pop("blender_cache")

        exit_val = BAT.test_blender_addon(addon_path=addon, blender_revision=blender_rev, config=config)
    except Exception as e:
        print(e)
        exit_val = 1

    print("---------------------------------------- RUN TESTS END ---------------------------------------------")
    sys.exit(exit_val)


main()