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

#include "pvtools.h"
#include "delay.h"
#include <cmath>

void DelayDistrib::InitDelta(double x) {
    maxPath = x;
    phi_x.clear();
}

void DelayDistrib::InitShape(double max, list<float> shape) {
    if (shape.size() < 2)
        throw ("Error: delay shape should consist of at least 2 values");
    double factor = max / (shape.size() - 1);
    phi_x.clear();
    int index = 0;
    for (list<float>::iterator si = shape.begin(); si != shape.end(); ++si) {
        phi_x[index * factor] = *si;
        ++index;
    }

    PHI_x.clear();
    map<double, double>::iterator pxi = phi_x.begin(), prev = pxi;
    double Px = 0;
    PHI_x[0] = 0;
    for (++pxi; pxi != phi_x.end(); ++pxi) {
        Px += (prev->second + pxi->second) * (pxi->first - prev->first) / 2;
        PHI_x[pxi->first] = Px;
        ++prev;
    }
    maxPHI = PHI_x.rbegin()->second;

    x_PHI.clear();
    for (map<double, double>::iterator Pxi = PHI_x.begin(); Pxi != PHI_x.end(); ++Pxi)
        x_PHI[Pxi->second] = Pxi->first;
}

double DelayDistrib::Sample() {
    if (phi_x.empty())
        return maxPath;
    double P = uniform() * maxPHI;
    map<double, double>::iterator ub = x_PHI.upper_bound(P), lb = ub;
    if (ub == x_PHI.end())
        throw ("Internal error: ub x_PHI out of range");
    if (ub == x_PHI.begin())
        return 0;
    --lb;
    double a = phi_x[lb->second], b = phi_x[ub->second], d = ub->second - lb->second;
    if (a == b)
        return lb->second + (P - lb->first) / a;
    return lb->second + (sqrt(a * a + 2 * (b - a) * (P - lb->first) / d) - a) * d / (b - a);
}


// huh() {
//   //Calculate targetDelayDistrib
//   if(argRead.delayShapeDistribution.empty()) {
//     argRead.delayShapeDistribution.push_back(2);
//     argRead.delayShapeDistribution.push_back(2);
//     argRead.delayShapeDistribution.push_back(1);
//   }
//   vector<double> delayShape(argRead.delayShapeDistribution.size());
//   int index=0;
//   for(list<float>::iterator si=argRead.delayShapeDistribution.begin(); si!=argRead.delayShapeDistribution.end(); ++si)
//     delayShape[index++]=*si;
//   Globals::targetDelayDistrib.resize(argRead.maxPathLength+1);
//   Globals::targetDelayDistrib[0]=delayShape[0];
//   Globals::targetDelayDistrib[argRead.maxPathLength]=delayShape[delayShape.size()-1];
//   double weight=Globals::targetDelayDistrib[0]+Globals::targetDelayDistrib[argRead.maxPathLength];
//   for(int d=1; d<argRead.maxPathLength; ++d) {
//     double i=double(d)*(delayShape.size()-1)/argRead.maxPathLength;
//     index=int(i);
//     Globals::targetDelayDistrib[d]=(i-index)*delayShape[index+1]+(index+1-i)*delayShape[index];
//     weight+=Globals::targetDelayDistrib[d];
//   }
//   for(int d=0; d<=argRead.maxPathLength; ++d)
//     Globals::targetDelayDistrib[d]/=weight;
// }

