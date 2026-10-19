# DW9714 VCM DKMS module

The OX05B1S camera module on this system uses a Dongwoon DW9714 voice coil
motor at I2C address 0x0c. The Raspberry Pi kernel image does not ship the
`dw9714` driver, and the stock `dw9807-vcm` driver does not match the
`dongwoon,dw9714` compatible string.

`dw9714.c` is imported unmodified from `raspberrypi/linux` branch
`rpi-6.18.y`, `drivers/media/i2c/dw9714.c`.

## Install

```sh
sudo cp -a . /usr/src/dw9714-0.1.0
sudo dkms add -m dw9714 -v 0.1.0
sudo dkms build -m dw9714 -v 0.1.0
sudo dkms install -m dw9714 -v 0.1.0
```

Then enable the VCM in the OX05B1S overlay:

```
dtoverlay=ox05b1s,cam0,4lane,vcm
```

and reboot. Verify with:

```sh
dmesg | grep -i dw9714
media-ctl -p -d /dev/media0
v4l2-ctl -d /dev/v4l-subdev<N> --list-ctrls
```

The lens entity must have function `MEDIA_ENT_F_LENS` and the subdevice must
expose `focus_absolute` with a range of 0-1023.

## Interactive focus console

`focus-console.py` provides an interactive terminal UI for the VCM. It finds
the lens subdevice automatically and moves the focus with the arrow keys:

```sh
./focus-console.py
```

Use a specific subdevice or a different arrow step if needed:

```sh
./focus-console.py --device /dev/v4l-subdev3 --step 8
```

Controls:

| Key | Action |
| --- | --- |
| Up / Down | Move focus by 16 (or `--step`) |
| `+` / `-` | Move focus by 1 |
| Page Up / Page Down | Move by 8x the step |
| `r` | Reset to the control default |
| `q` | Quit |

The script keeps the subdevice open while it runs, so the VCM stays powered
and the lens remains at the selected position. When the script exits, the
driver parks the lens at 0 and remembers the last value. The next time the
device is opened, the driver ramps back to that value.

Stop libcamera or set the autofocus mode to manual while using the console,
otherwise the AF algorithm will move the lens independently.

Dependencies: `python3` and `v4l-utils` (`v4l2-ctl`).
