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

#ifndef _H_Modules
#define _H_Modules

#include <string>
#include <list>
#include <map>
#include <set>
#include <vector>
#include <fstream>
#include "libraries.h"
#include "argread.h"

using namespace std;

class CounterMap {
public:
    CounterMap() : next(0) {}

    int operator[](void *p);

private:
    map<void *, int> counterMap;
    int next;
};

class ModuleType : public Cell {
public:
    ModuleType() : Cell(-1, -1, -1), number(0) {}

    void CompleteRegions();

    class Module *GetInstance();

    void GetIO(int size, int &i, int &o);

    //void GetT(int size, int &t);
    int GetMaxT(int size);

    void PutIO(int size, int i, int o);

    const string &InstanceName() { return instanceName; }

    void WriteRtd(const string &name);

    void WriteDat(const string &name);

    void WriteRegions(ofstream &out, string prefix = "");

    virtual int NumBlocks() { return numBlocks; }

    virtual bool Sequential() { return 1; }

private:
    struct TreeNode;
    struct CompoundNode;
    struct LibrarycellNode;
    struct MacrocellNode;
    struct DistribBucket;

    void InitializeForrest();

    void InsertIntoForrest(TreeNode *);

    void DeleteNode(TreeNode *);

    void BuildPartitionTree();

    void DeletePartitionTree();

    void FillBuckets();

    void WriteDatLine(ofstream &out, double B, double tgT, double tgI, double tgO, double tgG, double tgSdevT,
                      double tgSdevG,
                      double T, double I, double O, double g, double sdevT, double sdevG);

    void WriteDatWord(ofstream &out, double v, bool g = 0);

    void
    GetMeanIO(double size, double &meanT, double &meanI, double &meanO, double &meanG, double &sigmaT, double &sigmaG);

    DistribBucket &DistributionBucket(int size);

    void InitializeInstanceName();

private:
    struct Region {
        Region() : meanT(-1), sigmaT(-1), p(10), q(10), meanG(-1), sigmaG(-1) {}

        double meanT, sigmaT;
        double p, q;
        double meanG, sigmaG;
        double g_factor;
    };

    int number;
    string instanceName;
    list<string> libraries;
    list<int> distribution;
    map<int, Region> regions;
    int numBlocks;
public:
    typedef pair<int, int> IntPair;
private:
    struct DistribBucket {
        DistribBucket() : sumT(0), sumG(0), number(0) {}

        void AddData(int T, double g) {
            sumT += T;
            sumG += g;
            ++number;
        }

        double MeanT() { return double(sumT) / number; }

        double MeanG() { return double(sumG) / number; }

        unsigned long sumT;
        double sumG;
        unsigned int number;
        double newMeanT;
        double newMeanG;
    };

    map<int, DistribBucket> distributionBuckets;
    multimap<IntPair, TreeNode *> forrest;
    map<int, list<TreeNode *> > buckets;
    bool rtdWritten;
    bool datWritten;

    friend void ParseGnlFile();
};

inline bool operator<(ModuleType::IntPair &a, ModuleType::IntPair &b) {
    return a.first < b.first || (a.first == b.first && a.second < b.second);
}

class Module {
public:
    Module(Librarycell *cell);

    Module(Module *modA, Module *modB, ModuleType *modType);

    ~Module();

    void PostProcess(ModuleType *modType);

    int Size() { return area; }

    int NumBlocks() { return numBlocks; }

    int NumInputs() { return numInputs; }

    int NumOutputs() { return numOutputs; }

    int TotalPinCount();

    void CheckConsistency();

private:
    void Merge(Module *

    module);

    void WriteHnl(const string &name, ModuleType *modType);

    void WriteNetD(const string &name);

    void WriteNets(const string &name, ModuleType *modType);

    void WriteNetD2(const string &name);

    void WriteInfo(const string &name, ModuleType *modType);

    void WriteInfoHeader(ofstream &info, ModuleType *modType, string prefix = "");

    void WritePlots(const string &name, ModuleType *modType);

    void WriteTree(const string &name, ModuleType *modType);

    void WritePtree(const string &name, ModuleType *modType);

    void WriteBlifSimple(const string &name, ModuleType *modType);

private:
    struct Block;
    struct Net;
    struct InputNet;
    struct OutputNet;
    typedef pair<Block *, unsigned int> Terminal;
    list<Block *> blocks;
    list<InputNet *> inputs;
    list<OutputNet *> outputs;
    list<OutputNet *> internalNets;
    int area;
    int weight;
    int numBlocks;
    int numInputs;
    int numOutputs;
    int number;
    friend struct Net;
    friend struct InputNet;
    friend struct OutputNet;
};

struct Module::Block {
    Block(Librarycell *c) : inputs(c->I()), outputs(c->O()), cell(c) {}

    void CheckConsistency();

    vector<class Net *> inputs;
    vector<class OutputNet *> outputs;
    Librarycell *cell;
    int moduleNumber;
};

struct Module::Net {
public:
    void Join(InputNet *inputNet);

    void CheckConsistency();

    void WriteNetD(ofstream &out, CounterMap &cellMap);

    void WriteNets(ofstream &out, CounterMap &cellMap);

    list<Terminal> sinks;
};

struct Module::InputNet : public Module::Net {
public:
    InputNet(double minl, double maxl) : requiredMinLength(minl), allowedMaxLength(maxl) {}

    bool Join(InputNet *inputNet);

    void WriteNetD(ofstream &out, CounterMap &cellMap, int &padCounter);

    void WriteNets(ofstream &out, CounterMap &cellMap, int &padCounter);

    void WriteNetD2(ofstream &out, CounterMap &cellMap, int &padCounter);

public:
    double requiredMinLength;
    double allowedMaxLength;
    map<OutputNet *, double> controllableOutputs;
};

struct Module::OutputNet : public Module::Net {
public:
    OutputNet(double l) : source(Terminal(0, 0)), maxLength(l) {}

    void MakeInternal(Module *modA, Module *modB,
                      Module *modC); //TODO used to be: void OutputNet::MakeInternal(Module *modA, Module *modB, Module *modC);
    bool
    Join(InputNet *inputNet, Module *modA, Module *modB, Module *modC, double delayScaleFactor, ModuleType *modType);

    void AddFlop(Module *modA, Module *modB, Module *modC);

    void CheckConsistency();

    void WriteNetD(ofstream &out, CounterMap &cellMap, int &padCounter, bool external = 0);

    void WriteNets(ofstream &out, CounterMap &cellMap, int &padCounter, bool external = 0);

    void WriteNetD2(ofstream &out, CounterMap &cellMap, int &padCounter, bool external = 0);

public:
    Terminal source;
    double maxLength;
};

class ModuleType::TreeNode {
public:
    virtual int Size() = 0;

    virtual int NumBlocks() = 0;

    virtual int NumInputs() = 0;

    virtual int NumOutputs() = 0;

    int NumTerminals() { return NumInputs() + NumOutputs(); }

    double GFraction() { return double(NumOutputs()) / (NumInputs() + NumOutputs()); }

    virtual Module *BuildModule(ModuleType *modType) = 0;

    virtual void FillBucketsWithTree(map<int, list<TreeNode *> > &buckets);

    virtual void AddRtdData(map<int, map<int, int> > &rtd) = 0;
};

class ModuleType::CompoundNode : public ModuleType::TreeNode {
public:
    CompoundNode(TreeNode *l, TreeNode *r) : left(l), right(r), area(l->Size() + r->Size()),
                                             numBlocks(l->NumBlocks() + r->NumBlocks()), numInputs(-1),
                                             numOutputs(-1) {}

    virtual int Size() { return area; }

    virtual int NumBlocks() { return numBlocks; }

    virtual int NumInputs() { return numInputs; }

    virtual int NumOutputs() { return numOutputs; }

    virtual Module *BuildModule(ModuleType *modType);

    virtual void FillBucketsWithTree(map<int, list<TreeNode *> > &buckets);

    virtual void AddRtdData(map<int, map<int, int> > &rtd);

private:
    TreeNode *left, *right;
    int area;
    int numBlocks;
    int numInputs;
    int numOutputs;

    friend void ModuleType::DeleteNode(TreeNode *);
};

class ModuleType::LibrarycellNode : public ModuleType::TreeNode {
public:
    LibrarycellNode(Librarycell *c) : cell(c) {}

    virtual int Size() { return cell->Size(); }

    virtual int NumBlocks() { return 1; }

    virtual int NumInputs() { return cell->I(); }

    virtual int NumOutputs() { return cell->O(); }

    virtual Module *BuildModule(ModuleType *modType);

    virtual void AddRtdData(map<int, map<int, int> > &rtd) { ++(rtd[1][cell->T()]); }

    //private:
    Librarycell *cell;
};

class ModuleType::MacrocellNode : public ModuleType::TreeNode {
public:
    MacrocellNode(ModuleType *m) : macroType(m) {}

    virtual int Size() { return macroType->Size(); }

    virtual int NumBlocks() { return macroType->NumBlocks(); }

    virtual int NumInputs() { return numInputs; }

    virtual int NumOutputs() { return numOutputs; }

    virtual Module *BuildModule(ModuleType *modType);

    virtual void AddRtdData(map<int, map<int, int> > &rtd) { ++(rtd[macroType->NumBlocks()][numInputs + numOutputs]); }

private:
    ModuleType *macroType;
    int numInputs;
    int numOutputs;
};

#endif //{_H_Modules}