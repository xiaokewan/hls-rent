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

Module *ModuleType::GetInstance() {
    lout << "Generating instance of module " << name << ".\n";
    if (Globals::circuit == this)
        Globals::progress = numBlocks;

    //initalize temp variables in ModuleType
    InitializeInstanceName();
    InitializeForrest();
    rtdWritten = 0;
    datWritten = 0;
    buckets.clear();
    distributionBuckets.clear();

    if (argRead.debugBits & debug::combine)
        dout << "\n*** Combinations ***\n";

    BuildPartitionTree();
    Module *module=forrest.begin()->second->BuildModule(this);

    if (argRead.showProgress)
        cout << "                                                 \r" << flush;

    module->PostProcess(this);
    DeletePartitionTree();

    if (argRead.debugBits & debug::consistency)
    module->CheckConsistency();
    return module;
}

void ModuleType::InitializeForrest() {
    if (!forrest.empty())
        throw ("Internal error: forrest not empty");
    list<int>::iterator di = distribution.begin();
    for (list<string>::iterator li = libraries.begin(); li != libraries.end(); ++li) {
        map<string, Library>::iterator it = Globals::libraries.find(*li);
        if (it == Globals::libraries.end())
            throw ("Internal error: unknown library");
        for (list<Cell *>::iterator ci = it->second.cells.begin(); ci != it->second.cells.end(); ++ci) {
            for (int i = 0; i < *di; ++i) {
                Librarycell *libcell = dynamic_cast<Librarycell *>(*ci);
                ModuleType *modType = dynamic_cast<ModuleType *>(*ci);
                if (libcell)
                    InsertIntoForrest(new LibrarycellNode(libcell));
                else if (modType)
                    InsertIntoForrest(new MacrocellNode(modType));
                else
                    throw ("Internal error: cell should be libcell or macrocell");
            }
            ++di;
        }
    }
}

void ModuleType::BuildPartitionTree() {
    while (forrest.size() > 1) {
        TreeNode *n1 = forrest.begin()->second;
        forrest.erase(forrest.begin());

        LibrarycellNode *lc1 = dynamic_cast<LibrarycellNode *>(n1);
        if (lc1 && lc1->cell->Sequential() && !argRead.combineAccordingToSize)
            InsertIntoForrest(n1);
        else {
            TreeNode *n2 = forrest.begin()->second;
            forrest.erase(forrest.begin());

            if (n2->NumBlocks() == 1 && n1->NumBlocks() > 1) {
                //swap n1 and n2
                TreeNode *temp = n1;
                n1 = n2;
                n2 = temp;
            }
            if (n1->NumBlocks() == 1 && n2->NumBlocks() >= 1 && (n1->NumTerminals() > GetMaxT(n2->NumBlocks()) ||
                                                                 n2->NumBlocks() == 1 &&
                                                                 n2->NumTerminals() > GetMaxT(1))) {
                InsertIntoForrest(n1);
                InsertIntoForrest(n2);
            } else {
                LibrarycellNode *lc2 = dynamic_cast<LibrarycellNode *>(n2);
                if (lc2 && lc2->cell->Sequential() && n1->NumBlocks() <= argRead.minSeqBlocks) {
                    InsertIntoForrest(n1);
                    InsertIntoForrest(n2);
                } else {
                    InsertIntoForrest(new CompoundNode(n1, n2));
                }
            }
        }
    }
}

void ModuleType::DeletePartitionTree() {
    if (forrest.size() != 1)
        throw ("Internal error: forrest is not a tree");
    DeleteNode(forrest.begin()->second);
    forrest.clear();
}

inline void ModuleType::InsertIntoForrest(TreeNode *node) {
    int indexA = 0, indexB = 0;
    if (argRead.combineAccordingToSize)
        indexA = node->Size();
    multimap<IntPair, TreeNode *>::iterator f = forrest.upper_bound(IntPair(indexA, -1));
    if (f != forrest.end())
        indexB = f->first.second;
    forrest.insert(pair<IntPair, TreeNode *>(IntPair(indexA, randomNumber(indexB, INT_MAX)), node));
}

void ModuleType::DeleteNode(TreeNode *node) {
    CompoundNode *compoundNode = dynamic_cast<CompoundNode *>(node);
    if (compoundNode) {
        DeleteNode(compoundNode->left);
        DeleteNode(compoundNode->right);
    }
    delete node;
}

Module *ModuleType::LibrarycellNode::BuildModule(ModuleType *modType) {
    return new Module(cell);
}

Module *ModuleType::MacrocellNode::BuildModule(ModuleType *modType) {
    Module *module=macroType->GetInstance();
    Globals::hierarchy[modType->InstanceName()].push_back(macroType->InstanceName());
    numInputs =module->NumInputs();
    numOutputs =module->NumOutputs();
    return module;
}

Module *ModuleType::CompoundNode::BuildModule(ModuleType *modType) {
    Module *module=new Module(left->BuildModule(modType), right->BuildModule(modType), modType);
    area =module->Size();
    numBlocks =module->NumBlocks();
    numInputs =module->NumInputs();
    numOutputs =module->NumOutputs();
    if (argRead.showProgress) {
        cout << "Module count: " << Globals::progress << "                    \r" << flush;
        --Globals::progress;
    }
    return module;
}

void Module::PostProcess(ModuleType *modType) {
    //Write modules
    string name = modType->InstanceName();
    list<string> &formats = (Globals::circuit == modType) ? argRead.outputFormats : argRead.outputMacrocellFormats;
    for (list<string>::iterator fi = formats.begin(); fi != formats.end(); ++fi) {
        if (*fi == "hnl")
            WriteHnl(name, modType);
        else if (*fi == "netD")
            WriteNetD(name);
        else if (*fi == "netD2")
            WriteNetD2(name);
        else if (*fi == "nets")
            WriteNets(name, modType);
        else if (*fi == "info")
            WriteInfo(name, modType);
        else if (*fi == "plot")
            WritePlots(name, modType);
        else if (*fi == "rtd")
            modType->WriteRtd(name);
        else if (*fi == "dat")
            modType->WriteDat(name);
        else if (*fi == "tree")
            WriteTree(name, modType);
        else if (*fi == "ptree")
            WritePtree(name, modType);
        else if (*fi == "blif")
            WriteBlifSimple(name, modType);
    }

    //Check for target number of pins and g_fraction
    if (!argRead.noWarnings) {
        int numPins = numInputs + numOutputs, I, O, targetPins;
        modType->GetIO(area, I, O);
        targetPins = I + O;
        double gFrac = double(numOutputs) / numPins, targetGFrac = double(O) / targetPins;
        if (fabs(double(numPins - targetPins)) / targetPins * 100 > argRead.maxPinError)
            lerr << "Warning: error on number of pins exceeds " << argRead.maxPinError << "%: " << numPins << " ( "
                 << targetPins << " ).\n";
        if (fabs(double(gFrac - targetGFrac)) / targetGFrac * 100 > argRead.maxFracError)
            lerr << "Warning: error on final output fraction exceeds " << argRead.maxFracError << "%: " << gFrac
                 << " ( " << targetGFrac << ").\n";
    }
}

void ModuleType::InitializeInstanceName() {
    instanceName = name;
    if (Globals::circuit != this)
        instanceName += stringPrintf("_%02d", ++number);
}