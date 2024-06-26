import sys
import os
import subprocess
import threading
import random


def update_mphalport(target):
    if target == 'esp8266':
        mphalport_path = f'lib/micropython/ports/{target}/esp_mphal.h'
    elif target == 'pic16bit':
        mphalport_path = f'lib/micropython/ports/{target}/pic16bit_mphal.h'
    elif target == 'teensy':
        mphalport_path = f'lib/micropython/ports/{target}/teensy_hal.h'
    else:
        mphalport_path = f'lib/micropython/ports/{target}/mphalport.h'

    if not os.path.exists(mphalport_path):
        raise RuntimeError(mphalport_path)

    with open(mphalport_path, 'rb') as f:
        data = f.read().decode('utf-8')

    if '#ifndef _MPHALPORT_H_' not in data:
        data = f'#ifndef _MPHALPORT_H_\n#define _MPHALPORT_H_\n{data}\n#endif /* _MPHALPORT_H_ */\n'
        with open(mphalport_path, 'wb') as f:
            f.write(data.encode('utf-8'))


def generate_manifest(script_dir, lvgl_api, manifest_path, displays, indevs, frozen_manifest, *addl_manifest_files):
    if not os.path.exists('build'):
        os.mkdir('build')

    manifest_files = [
        f"include('{os.path.abspath(manifest_path)}')"
    ]

    if frozen_manifest is not None:
        manifest_files.append(f"include('{frozen_manifest}')")

    if lvgl_api:
        api_path = f'{script_dir}/api_drivers/lvgl_api_drivers'
    else:
        api_path = f'{script_dir}/api_drivers/py_api_drivers'

    frozen_manifest_files = [
        f'{api_path}/frozen/display/display_driver_framework.py',
        f'{api_path}/frozen/indev/touch_calibration/touch_cal_data.py',
        f'{api_path}/frozen/indev/touch_calibration/touch_calibrate.py',
        f'{api_path}/frozen/indev/_indev_base.py',
        f'{api_path}/frozen/indev/button_framework.py',
        f'{api_path}/frozen/indev/encoder_framework.py',
        f'{api_path}/frozen/indev/keypad_framework.py',
        f'{api_path}/frozen/indev/pointer_framework.py',
        f'{api_path}/fs_driver.py',
        f'{script_dir}/api_drivers/common_api_drivers/frozen/other/i2c.py',
        f'{script_dir}/api_drivers/common_api_drivers/frozen/other/io_expander_framework.py',
        f'{script_dir}/api_drivers/common_api_drivers/frozen/other/task_handler.py'
    ]

    for file in frozen_manifest_files:
        if not os.path.exists(file):
            raise RuntimeError(f'File not found "{file}"')

        print(file)
        file_path, file_name = os.path.split(file)
        entry = f"freeze('{file_path}', '{file_name}')"
        manifest_files.append(entry)

    for file in addl_manifest_files:
        if not os.path.exists(file):
            raise RuntimeError(f'File not found "{file}"')

        print(file)
        file_path, file_name = os.path.split(file)
        entry = f"freeze('{file_path}', '{file_name}')"
        manifest_files.append(entry)

    for file in indevs:
        if not os.path.exists(file):
            tmp_file = f'{script_dir}/api_drivers/common_api_drivers/indev/{file}.py'

            if not os.path.exists(tmp_file):
                raise RuntimeError(f'File not found "{file}"')

            file = tmp_file

        directory, file_name = os.path.split(file)
        extension_file = file_name.rsplit('.')[0] + '_extension.py'
        extension = os.path.join(directory, extension_file)
        if os.path.exists(extension):
            print(extension_file)
            entry = f"freeze('{directory}', '{extension_file}')"
            manifest_files.append(entry)

        print(file)
        file_path, file_name = os.path.split(file)
        entry = f"freeze('{file_path}', '{file_name}')"
        manifest_files.append(entry)

    for file in displays:
        if not os.path.exists(file):
            tmp_file = f'{script_dir}/api_drivers/common_api_drivers/display/{file}.py'

            if not os.path.exists(tmp_file):
                raise RuntimeError(f'File not found "{file}"')

            file = tmp_file

        print(file)
        file_path, file_name = os.path.split(file)
        entry = f"freeze('{file_path}', '{file_name}')"
        manifest_files.append(entry)

    manifest_files = '\n'.join(manifest_files)

    with open('build/manifest.py', 'w') as f:
        f.write(manifest_files)


def get_lvgl():
    cmd_ = [
        'git',
        'submodule',
        'update',
        '--init',
        '--',
        f'lib/lvgl'
    ]
    result, _ = spawn(cmd_, spinner=True)
    if result != 0:
        sys.exit(result)

    cmd_ = ['cd lib/lvgl && git checkout master']

    spawn(cmd_, out_to_screen=False)


def get_micropython():

    cmd_ = [
        'git',
        'submodule',
        'update',
        '--init',
        '--',
        f'lib/micropython'
    ]

    result, _ = spawn(cmd_, spinner=True)
    if result != 0:
        sys.exit(result)

    cmd_ = ['cd lib/micropython && git checkout v1.22.2']

    spawn(cmd_, out_to_screen=False)


def get_pycparser():
    cmd_ = [
        'git',
        'submodule',
        'update',
        '--init',
        '--',
        f'lib/pycparser'
    ]

    result, _ = spawn(cmd_)
    if result != 0:
        sys.exit(result)


def _busy_spinner(evnt):
    count = random.randint(1, 25)
    wait = random.randint(10, 100) * 0.001
    chars = '\\|/-'
    char_index = 0
    sys.stdout.write(chars[char_index] + '\r')
    sys.stdout.flush()

    while not evnt.is_set():
        evnt.wait(wait)
        count -= 1
        char_index += 1
        if char_index == 4:
            char_index = 0

        sys.stdout.write(f'{chars[char_index]}\r')
        sys.stdout.flush()

        if count == 0:
            count = random.randint(1, 25)
            wait = random.randint(10, 100) * 0.001


def spawn(cmd_, out_to_screen=True, spinner=False, env=None, cmpl=False):
    if env is None:
        env = os.environ

    if isinstance(cmd_[0], str):
        cmd_ = ' '.join(cmd_)
    else:
        cmd_ = ' && '.join(' '.join(c) for c in cmd_)

    p = subprocess.Popen(
        cmd_,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        env=env
    )

    os.set_blocking(p.stdout.fileno(), False)
    os.set_blocking(p.stderr.fileno(), False)

    event = threading.Event()

    if spinner:
        t = threading.Thread(target=_busy_spinner, args=(event,))
        t.daemon = True
        t.start()
    else:
        t = None

    output_buffer = []
    last_line_len = -1

    def _convert_line(lne):
        try:
            lne = lne.decode('utf-8')
        except UnicodeDecodeError:
            for char in lne:
                if 32 <= char <= 125 or char in (b'\r', b'\n'):
                    continue

                lne = lne.replace(char, b'')
            lne = lne.decode('utf-8')

        return lne

    try:
        while p.poll() is None:
            line = p.stdout.readline()
            if line is not None and line.strip():
                line = _convert_line(line.strip())
                output_buffer.append(line)

                if not spinner and out_to_screen:
                    if cmpl and line.startswith('[') and last_line_len != -1:
                        sys.stdout.write('\r')
                        if len(line) < last_line_len:
                            padding = ' ' * (last_line_len - len(line))
                        else:
                            padding = ''

                        sys.stdout.write(line + padding)
                        last_line_len = len(line)
                    else:
                        last_line_len = -1
                        sys.stdout.write(line + '\n')

                    sys.stdout.flush()

            line = p.stderr.readline()
            while line is not None and line.strip():
                if not spinner and out_to_screen and cmpl and last_line_len != -1:
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                    last_line_len = -1

                line = _convert_line(line.strip())
                output_buffer.append(line)

                if out_to_screen and not spinner:
                    sys.stderr.write(line + '\n')
                    sys.stderr.flush()

                line = p.stderr.readline()

    except KeyboardInterrupt:
        if t is not None:
            event.set()
            t.join()

        print()
        print(output_buffer)

        if not p.stdout.closed:
            p.stdout.close()

        if not p.stderr.closed:
            p.stderr.close()

        raise

    if not p.stdout.closed:
        p.stdout.close()

    if not p.stderr.closed:
        p.stderr.close()

    if t is not None:
        event.set()
        t.join()

    output_buffer = '\n'.join(output_buffer)

    if out_to_screen:
        if spinner:
            print(output_buffer)
        elif cmpl and last_line_len != -1:
            sys.stdout.write('\n')
            sys.stdout.flush()

    return p.returncode, output_buffer


def clean():
    spawn(clean_cmd)


def submodules():
    return_code, _ = spawn(submodules_cmd)
    if return_code != 0:
        sys.exit(return_code)


def compile():  # NOQA
    return_code, _ = spawn(compile_cmd)
    if return_code != 0:
        sys.exit(return_code)


def mpy_cross():
    return_code, _ = spawn(mpy_cross_cmd)
    if return_code != 0:
        sys.exit(return_code)


def build_manifest(target, script_dir, displays, indevs, frozen_manifest):
    update_mphalport(target)
    if target == 'teensy':
        manifest_path = f'lib/micropython/ports/{target}/manifest.py'
    else:
        manifest_path = f'lib/micropython/ports/{target}/boards/manifest.py'

    if not os.path.exists(manifest_path):
        raise RuntimeError(f'Unable to locate manifest file "{manifest_path}"')

    generate_manifest(script_dir, manifest_path, displays, indevs, frozen_manifest)


def parse_args(extra_args, lv_cflags, board):
    return extra_args, lv_cflags, board


mpy_cross_cmd = ['make', '-C', 'lib/micropython/mpy-cross']
cmd = [
    'make',
    '',
    f'-j {os.cpu_count()}',
    '-C'
]
clean_cmd = []
compile_cmd = []
submodules_cmd = []


def build_commands(target, extra_args, script_dir, lv_cflags, board):
    if target == 'samd':
        if lv_cflags is None:
            lv_cflags = '-DLV_USE_TINY_TTF=0'
        else:
            lv_cflags += ' -DLV_USE_TINY_TTF=0'

    cmd.extend([
        f'lib/micropython/ports/{target}',
        f'LV_PORT={target}',
    ])

    if lv_cflags is not None:
        cmd.append(f'LV_CFLAGS="{lv_cflags}"')

    if board is not None:
        if lv_cflags is not None:
            cmd.insert(5, f'BOARD={board}')
        else:
            cmd.append(f'BOARD={board}')

    cmd.append(f'USER_C_MODULES={script_dir}/ext_mod')
    cmd.extend(extra_args)

    clean_cmd.extend(cmd[:])
    clean_cmd[1] = 'clean'

    compile_cmd.extend(cmd[:])
    compile_cmd.pop(1)

    submodules_cmd.extend(cmd[:])
    submodules_cmd[1] = 'submodules'
