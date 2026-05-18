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

#ifndef _H_Libraries
#define _H_Libraries

#include <string>
#include <list>
#include <vector>
#include "argread.h"

using namespace std;

class Cell {
public:
    Cell(int i, int o, int a) : numInputs(i), numOutputs(o), area(a) {}

    Cell(string &n, int i, int o, int a) : name(n), numInputs(i), numOutputs(o), area(a) {}

    virtual ~Cell() {}

    int I() { return numInputs; }

    int O() { return numOutputs; }

    int T() { return numInputs + numOutputs; }

    double g() { return double(numOutputs) / (numInputs + numOutputs); }

    const string &Name() { return name; }

    int Size() { return area; }

    virtual int NumBlocks() = 0;

    virtual bool Sequential() = 0;

protected:
    string name;
    int numInputs;
    int numOutputs;
    int area;
};

class Librarycell : public Cell {
public:
    Librarycell(string &n, int i, int o, bool seq, int a, double d) : Cell(n, i, o, a), sequential(seq), delay(d),
                                                                      weight(1) {
        if (argRead.areaAsWeight) weight = area;
        area = 1;
    }

    virtual bool Sequential() { return sequential; }

    virtual int NumBlocks() { return 1; }

    double Delay() { return delay; }

    int Weight() { return weight; }

private:
    bool sequential;
    double delay;
    int weight;
};

class Library {
public:
    list<Cell *> cells;

    ~Library();
};

#endif //{_H_Libraries}