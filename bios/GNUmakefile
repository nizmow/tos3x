top_srcdir=..
subdir=bios

# 
# cross compiling
#
EVAL_CROSS := case `uname -s` in *MiNT*|*TOS*) echo no;; *) echo yes; esac
CROSS := $(shell $(EVAL_CROSS))

include $(top_srcdir)/GNUmakefile.cmn
include $(top_srcdir)/Makefile.sil
include optimize.mak

LIBS =

CPPFLAGS = -I$(top_srcdir)/common -I$(INC)
CFLAGS = $(OPTS) $(WARN)

all:: bios.a hadxbios.o m64_pci.o m64_isa.o medxbios.o

include $(top_srcdir)/config.mak
-include $(top_srcdir)/common/sections.mak

include SRCFILES

ifeq ($(USE_CROSS_ALCYON),1)
NO_BRANCH_OPT = -n
endif

bios.a: $(BIOS_OBJS) ${MAKEFILE}
	$(AM_V_AR)$(AR) $(ARFLAGS) $@ $(BIOS_OBJS)

startup.o: startup.S $(top_srcdir)/common/config.h header.h scrdmp.inc mmu030.inc romcrc.inc dma.inc intpriv.inc hadesmm.S medusamm.S
	$(AM_V_AS)$(AS) $(ASFLAGS) $(NO_BRANCH_OPT) $(CPPFLAGS) -c -o $@ $<

floppy.o: floppy.S hadflopp.S $(top_srcdir)/common/config.h
	$(AM_V_AS)$(AS) $(ASFLAGS) $(NO_BRANCH_OPT) $(CPPFLAGS) -c -o $@ $<

vars.o: $(top_srcdir)/common/vars.S $(top_srcdir)/common/config.h
	$(AM_V_AS)$(AS) $(ASFLAGS) $(CPPFLAGS) -c -o $@ $<

tosvars.o: $(top_srcdir)/common/tosvars.S $(top_srcdir)/common/config.h
	$(AM_V_AS)$(AS) $(ASFLAGS) $(CPPFLAGS) -c -o $@ $<

keytbl.o: $(top_srcdir)/common/config.h
monster.o: monster.S $(top_srcdir)/common/config.h

hadxbios.o: hadxbios.S $(FPSP060)
m64_isa.o: m64_isa.S m64_pci.S

prtkeys$(EXEEXT): prtkeys.o
	$(AM_V_LD)${LD} ${LDFLAGS} -o $@ prtkeys.o

ifeq ($(USE_CROSS_ALCYON),1)
blkdev.o: blkdev.c
	$(AM_V_CC)$(CC) $(CFLAGS) $(CPPFLAGS) ${RUN_OPTIMIZE_${$*_OPTIMIZE}} -c -S -o $*.s $<
	$(AM_V_at)$(SUBSTLMUL)
	$(AM_V_at)$(AS) $(ASFLAGS) -c $*.s
	$(AM_V_at)$(RM) $*.s
endif

check::
	@:

dist::
	$(CP) -a $(SRCS) $(EXTRA_DIST1) $(EXTRA_DIST2) $(top_srcdir)/$(DISTDIR1)/$(subdir)
	$(CP) -a $(EXTRA_DIST2) $(top_srcdir)/$(DISTDIR2)/$(subdir)

dosdir::
	$(CP) -a $(SRCS) $(EXTRA_DIST1) $(DOSDIR)/$(subdir)

clean:
	$(RM) *.o *.a *.ndx $(PROGRAMS) $(top_srcdir)/common/config.h

distclean: clean
	$(RM) $(top_srcdir)/common/sections.mak
