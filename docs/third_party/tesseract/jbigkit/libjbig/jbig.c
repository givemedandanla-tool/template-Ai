/*
 *  Portable JBIG image compression library
 *
 *  Copyright 1995-2014 -- Markus Kuhn -- http://www.cl.cam.ac.uk/~mgk25/
 *
 *  This module implements a portable standard C encoder and decoder
 *  using the JBIG1 lossless bi-level image compression algorithm
 *  specified in International Standard ISO 11544:1993 and
 *  ITU-T Recommendation T.82. See the file jbig.txt for usage
 *  instructions and application examples.
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 * 
 *  If you want to use this program under different license conditions,
 *  then contact the author for an arrangement.
 */

#ifdef DEBUG
#include <stdio.h>
#else
#define NDEBUG
#endif

#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "jbig.h"

#define MX_MAX  127    /* maximal supported mx offset for
			* adaptive template in the encoder */

#define TPB2CX  0x195  /* contexts for TP special pixels */
#define TPB3CX  0x0e5
#define TPDCX   0xc3f

/* marker codes */
#define MARKER_STUFF    0x00
#define MARKER_RESERVE  0x01
#define MARKER_SDNORM   0x02
#define MARKER_SDRST    0x03
#define MARKER_ABORT    0x04
#define MARKER_NEWLEN   0x05
#define MARKER_ATMOVE   0x06
#define MARKER_COMMENT  0x07
#define MARKER_ESC      0xff

/* loop array indices */
#define STRIPE  0
#define LAYER   1
#define PLANE   2

/* special jbg_buf pointers (instead of NULL) */
#define SDE_DONE ((struct jbg_buf *) -1)
#define SDE_TODO ((struct jbg_buf *) 0)

/* object code version id */

const char jbg_version[] = 
  "JBIG-KIT " JBG_VERSION " -- (c) 1995-2014 Markus Kuhn -- "
  "Licence: " JBG_LICENCE "\n";

/*
 * The following array specifies for each combination of the 3
 * ordering bits, which ii[] variable represents which dimension
 * of s->sde.
 */
static const int iindex[8][3] = {
  { 2, 1, 0 },    /* no ordering bit set */
  { -1, -1, -1},  /* SMID -> illegal combination */
  { 2, 0, 1 },    /* ILEAVE */
  { 1, 0, 2 },    /* SMID + ILEAVE */
  { 0, 2, 1 },    /* SEQ */
