* Minimal startup for the native GEMDOS probes (no libc heap/argv setup).
* Keep the stack inside our BSS before releasing the initial all-RAM TPA.
        xdef    _start
        xdef    __sovf
        xref    _main
        xref    _end
        text
_start:
        move.l  4(sp),a5
        lea     stacktop,sp
        suba.l  a6,a6
* _end includes every linked object's BSS/commons, not just our stack.
        move.l  #_end,d0
        sub.l   a5,d0
        move.l  d0,-(sp)
        move.l  a5,-(sp)
        clr.w   -(sp)
        move.w  #$4a,-(sp)
        trap    #1
        lea     12(sp),sp
        tst.l   d0
        bne.s   failed
        jsr     _main
        move.w  d0,-(sp)
        move.w  #$4c,-(sp)
        trap    #1
failed:
        move.l  #badstart,-(sp)
        move.w  #9,-(sp)
        trap    #1
        addq.l  #6,sp
        move.w  #1,-(sp)
        move.w  #$4c,-(sp)
        trap    #1
__sovf:
        bra.s   failed
        data
badstart:
        dc.b    'FAIL startup/stack',13,10,0
        even
        bss
        ds.b    8192
stacktop: ds.w 0
