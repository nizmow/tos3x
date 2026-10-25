#
# TOS version
# This must be the hexadecimal (bcd-encoded) number, but without any prefix
# currently 3.06, 2.06 and 2.08 is supported
#
TOSVERSION=306

#
# Country definition
# valid countries are:
# us - USA
# de - Germany
# fr - France
# uk - United Kingdom
# es - Spain
# it - Italy
# se - Sweden
# sf - Switzerland (French)
# sg - Switzerland (German)
#
# sf and sg only affect the country code in ROM header
# uk uses uk keyboard, and us resources
# sg uses de keyboard and resources
# sf uses fr keyboard and resources
#
COUNTRY=de

#
# Set this 1 to build an exact binary image of an official
# ROM version. The Alcyon compiler must be used for that.
#
BINEXACT=1

# Enable automatic MonSTer alternate RAM on TOS 2.06 (requires BINEXACT=0).
# Limit this if another expansion occupies part of $400000-$BFFFFF.
# Mega STE builds automatically cap the selected size at 6 MiB.
MONSTER=0
MONSTER_RAM_MB=8

#
# Set this to 1 to build a RAM version relocated to 0x380000.
# Only the PL version uses this so far.
# Note that the PL version is not an official TOS, it is
# an image found on the net on several sites, and contains
# some patches for the BIOS.
# If you need to change the base address for such an image,
# common/sections.inc must be modified (search for RAMVERSION there)
#
RAMVERSION=0

#
# Set this to 1 to build a hades ROM. Only valid for TOSVERSION 3.06
#
HADES=0
# offset to Hades extensions from start of ROM
HADES_XBIOS=49000

#
# Set this to 1 to build a hades Medusa. Only valid for TOSVERSION 2.06
#
MEDUSA=0

-include $(top_srcdir)/localcnf.mak

ifneq ($(filter $(MONSTER),0 1),$(MONSTER))
$(error MONSTER must be 0 or 1)
endif
ifeq ($(MONSTER),1)
ifneq ($(TOSVERSION),206)
$(error MONSTER=1 requires TOSVERSION=206)
endif
ifneq ($(BINEXACT),0)
$(error MONSTER=1 requires BINEXACT=0)
endif
ifneq ($(RAMVERSION)$(HADES)$(MEDUSA),000)
$(error MONSTER=1 requires a standard ROM build: RAMVERSION=0 HADES=0 MEDUSA=0)
endif
ifeq ($(filter $(MONSTER_RAM_MB),2 4 6 8),)
$(error MONSTER_RAM_MB must be 2, 4, 6, or 8)
endif
endif

#
# Rules to recreate some files from definitions above
#
$(top_srcdir)/common/config.h: $(top_srcdir)/config.mak ${MAKEFILE}
	$(AM_V_GEN)echo '/* automatically generated - DO NOT EDIT */' > $@
	$(AM_V_at)echo '#ifndef __CONFIG_H__' >> $@
	$(AM_V_at)echo '#define __CONFIG_H__ 1' >> $@
	$(AM_V_at)echo '#define TOSVERSION 0x$(TOSVERSION)' >> $@
	$(AM_V_at)echo '#define ATOSVERSION $$$(TOSVERSION)' >> $@
	$(AM_V_at)echo '#define OS_COUNTRY CTRY_$(COUNTRY)' >> $@
	$(AM_V_at)echo '#ifdef __GNUC__' >> $@
	$(AM_V_at)echo '# define BINEXACT 0' >> $@
	$(AM_V_at)echo '#else' >> $@
	$(AM_V_at)echo '# define BINEXACT $(BINEXACT)' >> $@
	$(AM_V_at)echo '#endif' >> $@
	$(AM_V_at)echo '#define RAMVERSION $(RAMVERSION)' >> $@
	$(AM_V_at)echo '#define HADES $(HADES)' >> $@
	$(AM_V_at)echo '#define HADES_XBIOS $$$(HADES_XBIOS)' >> $@
	$(AM_V_at)echo '#define MEDUSA $(MEDUSA)' >> $@
	$(AM_V_at)echo '#define MONSTER $(MONSTER)' >> $@
	$(AM_V_at)echo '#define MONSTER_RAM_MB $(MONSTER_RAM_MB)' >> $@
	$(AM_V_at)echo '#define CT2 0' >> $@
	$(AM_V_at)echo '#include "ctrycode.h"' >> $@
	$(AM_V_at)echo '#if !BINEXACT' >> $@
	$(AM_V_at)echo '#include "localcnf.h"' >> $@
	$(AM_V_at)echo '#endif' >> $@
	$(AM_V_at)echo '#include "patchdef.h"' >> $@
	$(AM_V_at)echo '#include "nopatch.h"' >> $@
	$(AM_V_at)echo '#endif' >> $@

$(top_srcdir)/common/sections.mak: $(top_srcdir)/common/sections.inc $(top_srcdir)/common/config.h
	$(AM_V_GEN)$(CPP) -D__MAKEFILE__ $(top_srcdir)${BS}common${BS}sections.inc $(CPPOUT) sections.i
	$(AM_V_at)$(SED) -e 's/$(QBS)$$//g' -e '//d' sections.i > sections.1
	$(AM_V_at)$(BC) -q < sections.1 > $@
	$(AM_V_at)$(RM) sections.i sections.1
	$(AM_V_at)-touch $(top_srcdir)/common/localcnf.h

# check that TOSVERSION and COUNTRY are valid
all:: tosversion_$(TOSVERSION) country_$(COUNTRY)
	@:

country_us country_de country_fr country_uk country_es country_it country_se country_sf country_sg country_cz country_nl:
tosversion_206 tosversion_306 tosversion_208:
