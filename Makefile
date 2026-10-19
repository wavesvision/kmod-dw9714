# SPDX-License-Identifier: GPL-2.0-only
#
# Out-of-tree build for the DW9714 VCM driver.

KDIR ?= /lib/modules/$(shell uname -r)/build

.PHONY: all module clean

all: module

Kbuild:
	@echo "obj-m += dw9714.o" > $@

module: Kbuild
	@$(MAKE) -C $(KDIR) M=$(CURDIR) modules

clean:
	@$(MAKE) -C $(KDIR) M=$(CURDIR) clean
	@rm -f Kbuild Module.symvers modules.order
