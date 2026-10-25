/* Hardware smoke test: allocate and verify the largest alternate RAM block.
 * Standalone TOS program, built with the bundled Alcyon tools (no C runtime).
 * Only writes memory returned by Mxalloc(), never disk sectors or flash.
 */
    text
start:
    pea     banner
    bsr     puts
    addq.l  #4,sp
    move.w  #1,-(sp)
    move.l  #-1,-(sp)
    move.w  #$44,-(sp)
    trap    #1
    addq.l  #8,sp
    move.l  d0,d6
    bsr     hexout
    cmpi.l  #4,d6
    blt     no_ram
    move.w  #1,-(sp)
    move.l  d6,-(sp)
    move.w  #$44,-(sp)
    trap    #1
    addq.l  #8,sp
    tst.l   d0
    ble     no_ram
    movea.l d0,a5
    pea     testing
    bsr     puts
    addq.l  #4,sp
    move.l  #$55aa55aa,d7
    moveq   #1,d5
test_pass:
    movea.l a5,a0
    move.l  d6,d1
    lsr.l   #2,d1
fill:
    move.l  a0,d0
    eor.l   d7,d0
    move.l  d0,(a0)+
    subq.l  #1,d1
    bne.s   fill
    movea.l a5,a0
    move.l  d6,d1
    lsr.l   #2,d1
verify:
    move.l  a0,d0
    eor.l   d7,d0
    cmp.l   (a0)+,d0
    bne.s   bad_ram
    subq.l  #1,d1
    bne.s   verify
    not.l   d7
    dbf     d5,test_pass
    pea     passed
    bra.s   release
bad_ram:
    pea     failed
release:
    bsr     puts
    addq.l  #4,sp
    move.l  a5,-(sp)
    move.w  #$49,-(sp)
    trap    #1
    addq.l  #6,sp
    bra.s   finish
no_ram:
    pea     missing
    bsr     puts
    addq.l  #4,sp
finish:
    pea     keymsg
    bsr     puts
    addq.l  #4,sp
    move.w  #7,-(sp)
    trap    #1
    addq.l  #2,sp
    clr.w   -(sp)
    trap    #1

puts:
    move.l  4(sp),-(sp)
    move.w  #9,-(sp)
    trap    #1
    addq.l  #6,sp
    rts
hexout:
    lea     hexbuf,a0
    moveq   #7,d2
hexloop:
    rol.l   #4,d0
    move.w  d0,d1
    andi.w  #15,d1
    addi.b  #'0',d1
    cmpi.b  #'9',d1
    bls.s   hexdigit
    addq.b  #7,d1
hexdigit:
    move.b  d1,(a0)+
    dbf     d2,hexloop
    pea     hexbuf
    bsr     puts
    addq.l  #4,sp
    rts

    data
banner:  dc.b 13,10,'Largest alternate RAM block: $',0
hexbuf:  dc.b '00000000',13,10,0
testing: dc.b 'Testing allocated RAM (two address-pattern passes)...',13,10,0
passed:  dc.b 'PASS',13,10,0
failed:  dc.b 'FAIL: memory readback mismatch',13,10,0
missing: dc.b 'No alternate RAM available, or allocation failed.',13,10,0
keymsg:  dc.b 'Press a key to return to the desktop.',13,10,0
    even
