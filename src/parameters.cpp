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

#include "main.h"
#include "argread.h"
#include "debug.h"
#include "pvtools.h"
#include <cmath>

void ModuleType::CompleteRegions() {
    //add/complete region for B=1
    int totalT = 0;
    double totalG = 0;
    numBlocks = 0;
    area = 0;
    list<int>::iterator di = distribution.begin();
    for (list<string>::iterator li = libraries.begin(); li != libraries.end(); ++li) {
        list<Cell *> &cells = Globals::libraries[*li].cells;
        for (list<Cell *>::iterator ci = cells.begin(); ci != cells.end(); ++ci) {
            if (di == distribution.end())
                throw ("Internal error: incomplete distribution");
            totalT += (*ci)->T() * (*di);
            totalG += (*ci)->g() * (*di);
            numBlocks += (*ci)->NumBlocks() * (*di);
            area += (*ci)->Size() * (*di);
            ++di;
        }
    }
    if (di != distribution.end())
        throw ("Internal error: distribution too large");
    double meanT = double(totalT) / numBlocks, meanG = totalG / numBlocks, totalSqDivT = 0, totalSqDivG = 0;
    di = distribution.begin();
    for (list<string>::iterator li = libraries.begin(); li != libraries.end(); ++li) {
        list<Cell *> &cells = Globals::libraries[*li].cells;
        for (list<Cell *>::iterator ci = cells.begin(); ci != cells.end(); ++ci) {
            double divT = (*ci)->T() - meanT, divG = (*ci)->g() - meanG;
            totalSqDivT += divT * divT * (*di);
            totalSqDivG += divG * divG * (*di);
            ++di;
        }
    }
    double sigmaT = sqrt(totalSqDivT / numBlocks);
    double sigmaG = sqrt(totalSqDivG / numBlocks);
    if (regions.empty() || regions.begin()->first != 1)
        regions[1] = Region();
    if (regions[1].meanT < 0)
        regions[1].meanT = meanT;
    if (regions[1].sigmaT < 0)
        regions[1].sigmaT = sigmaT;
    if (regions[1].meanG < 0)
        regions[1].meanG = meanG;
    if (regions[1].sigmaG < 0)
        regions[1].sigmaG = sigmaG;

    //check size of end region
    if (regions.rbegin()->first != area)
        throw ("end region not specified, or wrong circuit size");
    if (numInputs >= 0 && numOutputs >= 0) {
        regions.rbegin()->second.meanT = numInputs + numOutputs;
        regions.rbegin()->second.meanG = double(numOutputs) / (numInputs + numOutputs);
    }

    //complete other regions
    for (map<int, Region>::iterator ri = ++regions.begin(); ri != regions.end(); ++ri) {
        if (ri->first > area)
            throw ("Error: region with too many gates specified");

        //get previous region
        map<int, Region>::iterator prev = ri;
        --prev;

        //check/complete meanT and p
        if (ri->second.meanT >= 0 && ri->second.p < 5)
            throw ("Error: cannot specify both meanT and p");
        if (ri->second.meanT >= 0)
            ri->second.p = log(ri->second.meanT / prev->second.meanT) / log(double(ri->first) / prev->first);
        else {
            if (ri->second.p >= 5)
                ri->second.p = 0.6;
            ri->second.meanT = prev->second.meanT * pow(double(ri->first) / prev->first, ri->second.p);
        }

        //check/complete sigmaT and q
        if (ri->second.sigmaT >= 0 && ri->second.q < 5)
            throw ("Error: cannot specify both sigmaT and q");

        if (ri->second.sigmaT >= 0) {
            if (ri->second.sigmaT < 0.01)
                ri->second.q = -100;
            else
                ri->second.q = log(ri->second.sigmaT / prev->second.sigmaT) / log(double(ri->first) / prev->first);
        } else {
            if (ri->second.q >= 5)
                ri->second.q = ri->second.p - 0.1;
            ri->second.sigmaT = prev->second.sigmaT * pow(double(ri->first) / prev->first, ri->second.q);
        }

        //check G-parameters and calculate in g_factor
        if (ri->second.meanG < 0)
            ri->second.meanG = 0.3;
        if (ri->second.sigmaG < 0)
            ri->second.sigmaG = 0.15;
        ri->second.g_factor = (ri->second.meanG - prev->second.meanG) / log(double(ri->first) / prev->first);
    }

    //complete I and O
    if (numInputs < 0)
        numInputs = int(regions.rbegin()->second.meanT * (1 - regions.rbegin()->second.meanG) + 0.5);
    if (numOutputs < 0)
        numOutputs = int(regions.rbegin()->second.meanT * regions.rbegin()->second.meanG + 0.5);
}

void ModuleType::GetIO(int size, int &i, int &o) {
    if (size >= Size()) {
        i = numInputs;
        o = numOutputs;
        return;
    }
    map<int, Region>::iterator ri = regions.lower_bound(size), prev;
    if (ri == regions.begin())
        ++ri;
    if (ri == regions.end())
        throw ("Internal error: size out of bound");
    prev = ri;
    --prev;
    //meanT=T(B_{r-1})*(B/B_{r-1})^p
    //sigma_T=sigma_T(B_{r-1})*(B/B_{r-1})^q
    //meanG=g(B_{r-1})+g_factor*log(B/B_{r-1})
    //sigmaG=cte over gebied
    double meanT = prev->second.meanT * pow(double(size) / prev->first, ri->second.p);
    double sigmaT = prev->second.sigmaT * pow(double(size) / prev->first, ri->second.q);
    double meanG = prev->second.meanG + ri->second.g_factor * log(double(size) / prev->first);
    double sigmaG = ri->second.sigmaG;

    //sample from difference of target and actual distribution
    DistribBucket &bucket = DistributionBucket(size);
    double T, g;
    if (int(bucket.number) < argRead.correctionThreshold) {
        T = gaussian(meanT, sigmaT);
        g = gaussian(meanG, sigmaG);
        bucket.newMeanT = meanT;
        bucket.newMeanG = meanG;
    } else {
        bucket.newMeanT += (meanT - bucket.MeanT()) * argRead.meanTCorrectionFactor;
        double newMeanG = (meanG - bucket.MeanG()) * argRead.meanGCorrectionFactor;
        if (newMeanG > meanG - 2 * sigmaG && newMeanG < meanG + 2 * sigmaG)
            bucket.newMeanG += newMeanG;
        T = gaussian(bucket.newMeanT, sigmaT);
        g = gaussian(bucket.newMeanG, sigmaG);
    }

    i = int(T * (1 - g) + 0.5);
    o = int(T * g + 0.5);
}

// void ModuleType::GetT(int size, int &t) {
//   if(size>=area) {
//     t=numInputs+numOutputs;
//     return;
//   }
//   map<int,Region>::iterator ri=regions.lower_bound(size),prev;
//   if(ri==regions.begin())
//     ++ri;
//   if(ri==regions.end())
//     throw("Internal error: size out of bound");
//   prev=ri;
//   --prev;
//   //meanT=T(B_{r-1})*(B/B_{r-1})^p
//   //sigma_T=sigma_T(B_{r-1})*(B/B_{r-1})^q
//   double meanT=prev->second.meanT*pow(double(size)/prev->first,ri->second.p);
//   double sigmaT=prev->second.sigmaT*pow(double(size)/prev->first,ri->second.q);

//   //sample from difference of target and actual distribution
//   DistribBucket &bucket=DistributionBucket(size);
//   double T;
//   if(int(bucket.number)<argRead.correctionThreshold) {
//     T=gaussian(meanT,sigmaT);
//     bucket.newMeanT=meanT;
//   } else {
//     bucket.newMeanT+=(meanT-bucket.MeanT())*argRead.meanTCorrectionFactor;
//     T=gaussian(bucket.newMeanT,sigmaT);
//   }

//   t=int(T+0.5);
// }

void ModuleType::GetMeanIO(double size, double &meanT, double &meanI, double &meanO, double &meanG, double &sigmaT,
                           double &sigmaG) {
    map<int, Region>::iterator ri = regions.lower_bound(int(size)), prev;
    if (ri == regions.begin())
        ++ri;
    if (ri == regions.end()) {
        ri = regions.lower_bound(area);
        size = area;
    }
    prev = ri;
    --prev;
    meanT = prev->second.meanT * pow(size / prev->first, ri->second.p);
    meanG = prev->second.meanG + ri->second.g_factor * log(size / prev->first);
    meanI = meanT * (1 - meanG);
    meanO = meanT * meanG;
    sigmaT = prev->second.sigmaT * pow(size / prev->first, ri->second.q);
    sigmaG = prev->second.sigmaG;
}

int ModuleType::GetMaxT(int size) {
    map<int, Region>::iterator ri = regions.lower_bound(int(size)), prev;
    if (ri == regions.begin())
        ++ri;
    if (ri == regions.end()) {
        ri = regions.lower_bound(area);
        size = area;
    }
    prev = ri;
    --prev;
    double meanT = prev->second.meanT * pow(size / prev->first, ri->second.p);
    double sigmaT = prev->second.sigmaT * pow(size / prev->first, ri->second.q);
    return int(meanT + argRead.minSigmaTFactor * sigmaT);
}

void ModuleType::PutIO(int size, int i, int o) {
    int T = i + o;
    double g = double(o) / T;
    DistributionBucket(size).AddData(T, g);
}

ModuleType::DistribBucket &ModuleType::DistributionBucket(int size) {
    return distributionBuckets[int(log(double(size)) / log(double(argRead.correctionBucketFactor)))];
}

