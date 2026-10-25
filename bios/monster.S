/*
 * MonSTer alternate RAM for TOS 2.06.
 *
 * Hardware references:
 * https://atari.joska.no/monster/ (M_ALTRAM usage and address conflicts)
 * https://github.com/emutos/emutos/blob/master/bios/memory2.c
 * https://github.com/emutos/emutos/blob/master/bios/machine.h
 *
 * The board enables RAM with a control-register read followed by two word
 * writes of the size in MiB. No RAM is assumed to be DMA-accessible.
 * Called in supervisor mode after GEMDOS initialization on every boot.
 */

#include "config.h"
#include "asmdefs.h"
#include "tosvars.inc"

    text
    xdef _monster_init
    xref _xmxalloc
    xref _xmaddalt
    xref _xmfree

_monster_init:
    movem.l d0-d7/a0-a6,-(sp)

    /* Hold Alt during a cold boot to leave the RAM/flash window alone. */
    btst    #3,ABSW(_shifty)
    bne     monster_done

    moveq   #MONSTER_RAM_MB,d6
    movea.l ABSW(_p_cookies),a0
    move.l  a0,d0
    beq     monster_done
monster_machine:
    move.l  (a0)+,d0
    beq.s   monster_probe
    cmpi.l  #$5f4d4348,d0           /* _MCH */
    bne.s   monster_next
    cmpi.l  #$00010010,(a0)        /* Mega STE: VME starts at $A00000 */
    bne.s   monster_probe
    cmpi.w  #6,d6
    bls.s   monster_probe
    moveq   #6,d6
    bra.s   monster_probe
monster_next:
    addq.l  #4,a0
    bra.s   monster_machine

monster_probe:
    /* Discard any bus-error frame using saved SP (68000 or long frame).
     * No calls or interrupts may disturb the saved registers in this window.
     */
    move.w  sr,d7
    ori.w   #$0700,sr
    movea.l ABSW(_buserror),a3
    movea.l sp,a4
    move.l  #monster_absent,ABSW(_buserror)
    lea.l   $fffffe00,a0
    move.w  (a0),d0
    move.w  d6,(a0)
    move.w  d6,(a0)
    move.l  a3,ABSW(_buserror)
    move.w  d7,sr

    /* Reuse an existing _FRB. Otherwise reserve a cookie slot and allocate
     * 64 KiB of ST-RAM, owned by the OS, for floppy/hard-disk DMA buffering.
     */
    moveq   #0,d3                  /* allocated a new buffer? */
    moveq   #0,d5                  /* cookies already in use */
    movea.l ABSW(_p_cookies),a5
monster_cookie:
    move.l  (a5),d0
    beq.s   monster_slot
    cmpi.l  #$5f465242,d0           /* _FRB */
    beq.s   monster_existing
    addq.l  #8,a5
    addq.l  #1,d5
    bra.s   monster_cookie
monster_existing:
    tst.l   4(a5)
    beq     monster_done           /* invalid existing buffer: do not add RAM */
    bra.s   monster_register
monster_slot:
    addq.l  #2,d5                  /* one new cookie plus the terminator */
    cmp.l   4(a5),d5               /* terminator value is jar capacity */
    bhi     monster_done
    clr.w   -(sp)                  /* MX_STRAM */
    move.l  #$10000,-(sp)
    jsr     _xmxalloc
    addq.l  #6,sp
    tst.l   d0
    ble     monster_done
    move.l  d0,d4
    moveq   #1,d3

monster_register:
    move.l  d6,d0
    swap    d0
    lsl.l   #4,d0                  /* MiB -> bytes */
    move.l  d0,-(sp)
    move.l  #$400000,-(sp)
    jsr     _xmaddalt
    addq.l  #8,sp
    tst.w   d0                     /* ERROR is a 16-bit Alcyon int */
    bne.s   monster_failed
    tst.w   d3
    beq.s   monster_done

    /* Publish the new terminator before making its previous slot live. */
    move.w  sr,d7
    ori.w   #$0700,sr
    clr.l   8(a5)
    move.l  4(a5),12(a5)
    move.l  d4,4(a5)
    move.l  #$5f465242,(a5)
    move.w  d7,sr
    bra.s   monster_done

monster_failed:
    tst.w   d3
    beq.s   monster_done
    move.l  d4,-(sp)
    jsr     _xmfree
    addq.l  #4,sp
    bra.s   monster_done

monster_absent:
    movea.l a4,sp
    move.l  a3,ABSW(_buserror)
    move.w  d7,sr
monster_done:
    movem.l (sp)+,d0-d7/a0-a6
    rts
