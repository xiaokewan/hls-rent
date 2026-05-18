/**************************************************************************
***
*** Copyright (c) 1998-2001 Peter Verplaetse, Dirk Stroobandt
***
***  Contact author: pvrplaet@elis.rug.ac.be
***  Affiliation:   Ghent University
***                 Department of Electronics and Information Systems
***                 St.-Pietersnieuwstraat 41
***                 9000 Gent, Belgium
***
***  Permission is hereby granted, free of charge, to any person obtaining
***  a copy of this software and associated documentation files (the
***  "Software"), to deal in the Software without restriction, including
***  without limitation
***  the rights to use, copy, modify, merge, publish, distribute, sublicense,
***  and/or sell copies of the Software, and to permit persons to whom the
***  Software is furnished to do so, subject to the following conditions:
***
***  The above copyright notice and this permission notice shall be included
***  in all copies or substantial portions of the Software.
***
*** THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
*** EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
*** OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
*** IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
*** CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT
*** OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
*** THE USE OR OTHER DEALINGS IN THE SOFTWARE.
***
***************************************************************************/

#ifndef _H_Gnl
#define _H_Gnl

#include <map>
#include "libraries.h"
#include "modules.h"
#include "delay.h"

using namespace std;

class Globals {
public:
    struct PtreeNode {
        PtreeNode(int p, int c1, int c2, int a, int b, int i, int o) : parent(p), child1(c1), child2(c2), area(a),
                                                                       numBlocks(b), inputs(i), outputs(0) {}

        int parent, child1, child2;
        int area, numBlocks;
        int inputs, outputs;
    };

    static map<string, Library> libraries;
    static Librarycell *flop;
    static ModuleType *circuit;
    static int progress;
    static map<string, list<string> > hierarchy;
    static string version;
    static DelayDistrib delays;
    static vector<double> targetDelayDistrib;
    static int moduleCounter;
    static list<PtreeNode> treeData;
};

void ParseGnlFile();

#endif //{_H_Gnl}