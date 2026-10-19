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
