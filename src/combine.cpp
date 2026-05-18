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
#include "pvtools.h"
#include "debug.h"

Module::~Module() {
    for (list<Block *>::iterator bi = blocks.begin(); bi != blocks.end(); ++bi)
        delete *bi;
    for (list<OutputNet *>::iterator ni = internalNets.begin(); ni != internalNets.end(); ++ni)
        delete *ni;
    for (list<InputNet *>::iterator ni = inputs.begin(); ni != inputs.end(); ++ni)
        delete *ni;
    for (list<OutputNet *>::iterator ni = outputs.begin(); ni != outputs.end(); ++ni)
        delete *ni;
}

Module::Module(Librarycell *cell) : numBlocks(1) {
    area = cell->Size();
    weight = cell->Weight();
    numInputs = cell->I();
    numOutputs = cell->O();
    Block *block = new Block(cell);
    block->moduleNumber = number;
    blocks.push_back(block);
    for (int n = 0; n < numInputs; ++n) {
        double maxDelay = Globals::delays.Sample(), minDelay = min(double(argRead.minPathLength), maxDelay / 2);
        if (!cell->Sequential()) {
            maxDelay -= cell->Delay();
            minDelay = 0;
        }
        InputNet *net = new InputNet(minDelay, maxDelay);
        inputs.push_back(net);
        net->sinks.push_back(Terminal(block, n));
        block->inputs[n] = net;
    }
    for (int n = 0; n < numOutputs; ++n) {
        OutputNet *net = new OutputNet(cell->Sequential() ? 0 : cell->Delay());
        outputs.push_back(net);
        net->source = Terminal(block, n);
        block->outputs[n] = net;
    }

    if (!argRead.allowLoops && !cell->Sequential()) {
        for (list<InputNet *>::iterator ii = inputs.begin(); ii != inputs.end(); ++ii)
            for (list<OutputNet *>::iterator oi = outputs.begin(); oi != outputs.end(); ++oi)
                (*ii)->controllableOutputs[*oi] = cell->Delay();
    }

    number = ++Globals::moduleCounter;
    Globals::treeData.push_back(Globals::PtreeNode(number, -1, -1, weight, numBlocks, numInputs, numOutputs));
}

Module::Module(Module *modA, Module *modB, ModuleType *modType) {
    //Get number of inputs and outputs of modA, modB and target module
    int ia = modA->numInputs;
    int ib = modB->numInputs;
    int oa = modA->numOutputs;
    int ob = modB->numOutputs;
    int par_ic, par_oc;
    area = modA->area + modB->area;
    weight = modA->weight + modB->weight;
    numBlocks = modA->numBlocks + modB->numBlocks;
    modType->GetIO(area, par_ic, par_oc);
    int ic = par_ic, oc = par_oc;

    double delayScaleFactor = min(1.0, log(double(Size())) /
                                       (argRead.pathLengthCutOff * log(double(Globals::circuit->Size())) / 100));

    //Make sure no pins or outputs have to be created (which would imply that the local rent>1)
    int minInputs = min(ia + ib, argRead.minimumInputs);
    int minOutputs = min(oa + ob, argRead.minimumOutputs);
    if (oc < minOutputs)
        oc = minOutputs;
    if (oc > oa + ob)
        oc = oa + ob;
    if (ic < minInputs)
        ic = minInputs;
    if (ic > ia + ib)
        ic = ia + ib;

    //Calculate number of internal and external connections
    int si, se;
    if (argRead.twoPointNets) {
        si = (oa + ob + ia + ib - oc - ic) / 2;
        if (si < 0)
            si = 0;
    } else if (oa + ob - oc > ia + ib - ic) {     //more outputs than inputs to be eliminated (se<0)?
        si = int((oa + ob - oc + ia + ib - ic) / 2.0 + 0.5);
        if (ia + ib - si < minInputs)
            si = ia + ib - minInputs;
    } else
        si = oa + ob - oc;
    if (si < 0)
        throw ("Internal error: si<0");
    if (argRead.twoPointNets)
        se = 0;
    else
        se = (ia + ib - ic) - si;
    if (se < 0)
        se = 0;

    //Make sure at least 1 connection is laid (when possible)
    if (se + si == 0 && !argRead.twoPointNets)
        se = 1;

    if (argRead.debugBits & debug::combine) {
        dout << "Combining modules -- ";
        dout << "B: " << modA->numBlocks << " " << modB->numBlocks << " " << numBlocks << ", ";
        dout << "T: " << (ia + oa) << " " << (ib + ob) << " " << (ic + oc) << ", ";
        dout << "I: " << ia << " " << ib << " " << ic << "(" << par_ic << "), ";
        dout << "O: " << oa << " " << ob << " " << oc << "(" << par_oc << "), ";
        dout << "se=" << se << ", si=" << si << endl;
    }

    //make connections by combining nets
    //  current schemes:
    //    * make external connections from A to B and from B to A in a random order
    //    * convert some of these connections to internal connections
    //    * make other external connections by combining inputs
    int external = 0, externalAtoB = 0;

    list<InputNet *>::iterator iai = modA->inputs.begin();
    list<InputNet *>::iterator ibi = modB->inputs.begin();
    list<OutputNet *>::iterator oai = modA->outputs.begin();
    list<OutputNet *>::iterator obi = modB->outputs.begin();

    if (argRead.debugBits & debug::combine)
        dout << "   phase 1: ";

    //loop over outputs of A and then over inputs of B, also
    //loop over outputs of B and then over inputs of A. Select a
    //connection at random and make that connection if allowed
    bool aToB, bToA, firstConnection = 1;
    while (external < se + si) {
        list<OutputNet *>::iterator toSplice;
        aToB = (oai != modA->outputs.end() && ibi != modB->inputs.end());
        bToA = (obi != modB->outputs.end() && iai != modA->inputs.end());

        if (!aToB && !bToA)
            break;
        if (!bToA || (aToB && (randomNumber(2) || firstConnection))) {
            //make AtoB connection if allowed, else move on
            if ((*oai)->Join(*ibi, modA, modB, this, delayScaleFactor, modType)) {
                toSplice = oai++;
                outputs.splice(outputs.begin(), modA->outputs, toSplice);
                modB->inputs.erase(ibi);
                ibi = modB->inputs.begin();
                ++external;
                ++externalAtoB;
            } else if (++ibi == modB->inputs.end()) {
                ibi = modB->inputs.begin();
                ++oai;
            }
        } else {
            //make BtoA connection if allowed, else move on
            if ((*obi)->Join(*iai, modB, modA, this, delayScaleFactor, modType)) {
                toSplice = obi++;
                outputs.splice(outputs.begin(), modB->outputs, toSplice);
                modA->inputs.erase(iai);
                iai = modA->inputs.begin();
                ++external;
            } else if (++iai == modA->inputs.end()) {
                iai = modA->inputs.begin();
                ++obi;
            }
        }

        firstConnection = 0;
    }

    if (argRead.debugBits & debug::combine) {
        dout << "A to B: " << externalAtoB << endl;
        dout << "            B to A: " << (external - externalAtoB) << ", total: " << external << endl;
        dout << "   phase 2: converting to internal nets: ";
    }

    //covert to internal nets
    randomizeList(outputs);
    int internal = 0;
    list<OutputNet *>::iterator li = outputs.begin();
    while (si > 0 && external > 0) {
        (*li)->MakeInternal(modA, modB, this);
        ++li;
        --si;
        --external;
        ++internal;
    }
    se -= external;
    internalNets.splice(internalNets.end(), outputs, outputs.begin(), li);

    if (argRead.debugBits & debug::combine) {
        dout << internal << ", se=" << se << ", si=" << si << endl;
        dout << "   phase 3: a + b: ";
    }

    //loop over inputs of ModuleA and inputs of Module B and combine
    int inputCombinations = 0;
    while (se > 0 && !modA->inputs.empty() && !modB->inputs.empty()) {
        modA->inputs.front()->Join(modB->inputs.front());
        inputs.splice(inputs.begin(), modA->inputs, modA->inputs.begin());
        modB->inputs.pop_front();
        --se;
        ++external;
        ++inputCombinations;
    }

    if (argRead.debugBits & debug::combine)
        dout << inputCombinations << ", se=" << se << endl;

    //Move remaining blocks and nets
    Merge(modA);
    Merge(modB);
    numInputs = modA->numInputs + modB->numInputs - external - internal;
    numOutputs = modA->numOutputs + modB->numOutputs - internal;

    //if allowed: make connections from the resulting module to itself
    if (!argRead.noLocalConnections &&
        log(double(Size())) / log(double(modType->Size())) * 100 > argRead.localConnectionCutOff) {
        randomizeList(inputs);
        randomizeList(outputs);
        external = 0;
        list<OutputNet *> newOutputs;
        list<InputNet *>::iterator ii = inputs.begin();
        list<OutputNet *>::iterator oi = outputs.begin();

        if (argRead.debugBits & debug::combine) {
            dout << "   local connections:\n";
            dout << "   phase 4: output connections: ";
        }

        while (external < se + si && oi != outputs.end() && ii != inputs.end()) {
            list<OutputNet *>::iterator toSplice;

            //make output connection if allowed, else move on
            if ((*oi)->Join(*ii, this, 0, this, delayScaleFactor, modType)) {
                toSplice = oi++;
                newOutputs.splice(newOutputs.begin(), outputs, toSplice);
                inputs.erase(ii);
                ii = inputs.begin();
                ++external;
            } else if (++ii == inputs.end()) {
                ii = inputs.begin();
                ++oi;
            }
        }

        if (argRead.debugBits & debug::combine) {
            dout << external << endl;
            dout << "   phase 5: converting to internal nets: ";
        }

        //covert to internal nets
        randomizeList(newOutputs);
        internal = 0;
        list<OutputNet *>::iterator li = newOutputs.begin();
        while (si > 0 && external > 0) {
            (*li)->MakeInternal(this, 0, 0);
            ++li;
            --si;
            --external;
            ++internal;
        }
        se -= external;
        internalNets.splice(internalNets.end(), newOutputs, newOutputs.begin(), li);

        if (argRead.debugBits & debug::combine) {
            dout << internal << ", se=" << se << ", si=" << si << endl;
            dout << "   phase 6: internal connections: ";
        }

        //combine inputs
        inputCombinations = 0;
        while (se > 0 && inputs.size() >= 2) {
            randomizeList(inputs);
            InputNet *input = inputs.front();
            inputs.pop_front();
            inputs.front()->Join(input);
            --se;
            ++external;
            ++inputCombinations;
        }

        if (argRead.debugBits & debug::combine)
            dout << inputCombinations << ", se=" << se << endl;

        outputs.splice(outputs.end(), newOutputs);
        numInputs -= external + internal;
        numOutputs -= internal;
    }

    //Store final number of inputs and outputs
    modType->PutIO(area, numInputs, numOutputs);

    if (argRead.debugBits & debug::combine) {
        if (numInputs != int(inputs.size()))
            throw ("Internal error: wrong number of inputs after combining");
        if (numOutputs != int(outputs.size()))
            throw ("Internal error: wrong number of outputs after combining");
        dout << "Result: I=" << numInputs << ", O=" << numOutputs << endl << endl;
    }

    randomizeList(inputs);
    randomizeList(outputs);

    //store partitioning tree data
    number = ++Globals::moduleCounter;
    Globals::treeData.push_back(
            Globals::PtreeNode(number, modA->number, modB->number, weight, numBlocks, numInputs, numOutputs));

    delete (modA);
    delete (modB);
}

void Module::Net::Join(InputNet *inputNet) {
    //Add inputNet's sinks to this net
    for (list<Terminal>::iterator ti = inputNet->sinks.begin(); ti != inputNet->sinks.end(); ++ti)
        ti->first->inputs[ti->second] = this;
    sinks.splice(sinks.end(), inputNet->sinks);
}

bool Module::InputNet::Join(InputNet *inputNet) {
    Net::Join(inputNet);

    //update controllableOutputs
    if (!argRead.allowLoops) {
        //add inputNet's controllableOutputs to thisInput's controllableOutputs
        for (map<OutputNet *, double>::iterator coi = inputNet->controllableOutputs.begin();
             coi != inputNet->controllableOutputs.end(); ++coi)
            controllableOutputs[coi->first] = max(controllableOutputs[coi->first], coi->second);
    }

    //update maxLength
    requiredMinLength = max(requiredMinLength, inputNet->requiredMinLength);
    allowedMaxLength = min(allowedMaxLength, inputNet->allowedMaxLength);

    delete inputNet;
    return 1;
}

bool Module::OutputNet::Join(InputNet *inputNet, Module *modA, Module *modB, Module *modC, double delayScaleFactor,
                             ModuleType *modType) {
    bool allowed = 1;
    //check if connection is allowed -- i.e. no loops are being generated
    if (!argRead.allowLoops && inputNet->controllableOutputs.find(this) != inputNet->controllableOutputs.end())
        allowed = 0;

    if (!argRead.allowLoops && !argRead.allowLongPaths) {
        //check if path is not too long
        if (maxLength > delayScaleFactor * inputNet->allowedMaxLength)
            allowed = 0;
        //check if path is not too short
        if (maxLength < delayScaleFactor * inputNet->requiredMinLength)
            return 0;
    }

    if (!allowed) {
        if (!argRead.dontInsertFlops && Globals::flop &&
            log(double(modC->Size())) / log(double(modType->Size())) * 100 > argRead.flopCutOff &&
            argRead.flopInsertProbability >= uniform())
            AddFlop(modA, modB, modC);
        else
            return 0;
    }

    Net::Join(inputNet);

    //loop over all the controllable outputs of inputNet and update the maxLength if necessary
    for (map<OutputNet *, double>::iterator coi = inputNet->controllableOutputs.begin();
         coi != inputNet->controllableOutputs.end(); ++coi)
        coi->first->maxLength = max(coi->first->maxLength, coi->second + maxLength);

    //update controllableOutputs
    if (!argRead.allowLoops && !argRead.allowLongPaths) {
        //loop over all the inputs, and add inputNet's controllableOutputs if thisOutput belongs to their controllableOutputs
        //also update the maxLengths of the inputs if necessary
        for (Module *mod = modA; mod; mod = (mod == modA) ? modB : (mod == modB) ? modC : 0)
            for (list<InputNet *>::iterator li = mod->inputs.begin(); li != mod->inputs.end(); ++li) {
                map<OutputNet *, double>::iterator co = (*li)->controllableOutputs.find(this);
                if (co != (*li)->controllableOutputs.end()) {
                    for (map<OutputNet *, double>::iterator it = inputNet->controllableOutputs.begin();
                         it != inputNet->controllableOutputs.end(); ++it)
                        (*li)->controllableOutputs[it->first] = max((*li)->controllableOutputs[it->first],
                                                                    co->second + it->second);
                    double len = inputNet->allowedMaxLength - co->second;
                    if (len < 0)
                        throw ("Internal error: allowedMaxLength<0");
                    if (len < (*li)->allowedMaxLength)
                        (*li)->allowedMaxLength = len;

                    len = max(0.0, inputNet->requiredMinLength - co->second);
                    if (len > (*li)->requiredMinLength)
                        (*li)->requiredMinLength = len;
                }
            }
    }

    delete inputNet;
    return 1;
}

void Module::OutputNet::MakeInternal(Module *modA, Module *modB, Module *modC) {
    if (!argRead.allowLoops) {
        //loop over all the inputs, and remove this output (if it belongs to their controllableOutputs)
        for (Module *mod = modA; mod; mod = (mod == modA) ? modB : (mod == modB) ? modC : 0)
            for (list<InputNet *>::iterator li = mod->inputs.begin(); li != mod->inputs.end(); ++li)
                (*li)->controllableOutputs.erase(this);
    }
}

void Module::Merge(Module *

module) {
blocks.
splice(blocks
.

end(),

module->blocks);
internalNets.
splice(internalNets
.

end(),

module->internalNets);
inputs.
splice(inputs
.

end(),

module->inputs);
outputs.
splice(outputs
.

end(),

module->outputs);
}

void Module::CheckConsistency() {
    lout << "Checking consistency.\n";
    if (numBlocks != int(blocks.size()))
        throw ("Internal error: number of blocks does not match");
    if (numInputs != int(inputs.size()))
        throw ("Internal error: number of module inputs does not match");
    if (numOutputs != int(outputs.size()))
        throw ("Internal error: number of module outputs does not match");
    int realArea = 0;
    for (list<Block *>::iterator bi = blocks.begin(); bi != blocks.end(); ++bi) {
        (*bi)->CheckConsistency();
        realArea += (*bi)->cell->Size();
    }
    if (area != realArea)
        throw ("Internal error: size does not match");
    for (list<InputNet *>::iterator ni = inputs.begin(); ni != inputs.end(); ++ni)
        (*ni)->CheckConsistency();
    for (list<OutputNet *>::iterator ni = outputs.begin(); ni != outputs.end(); ++ni)
        (*ni)->CheckConsistency();
    for (list<OutputNet *>::iterator ni = internalNets.begin(); ni != internalNets.end(); ++ni)
        (*ni)->CheckConsistency();
}

void Module::Block::CheckConsistency() {
    if (int(inputs.size()) != cell->I())
        throw ("Internal error: number of block inputs does not match");
    if (int(outputs.size()) != cell->O())
        throw ("Internal error: number of block inputs does not match");
    for (unsigned int i = 0; i < inputs.size(); ++i) {
        int count = 0;
        for (list<Terminal>::iterator ti = inputs[i]->sinks.begin(); ti != inputs[i]->sinks.end(); ++ti)
            if (ti->first == this && ti->second == i)
                ++count;
        if (count != 1)
            throw ("Internal error: net does not point back to block input terminal");
    }
    for (unsigned int o = 0; o < outputs.size(); ++o) {
        if (!outputs[o]->source.first)
            throw ("Internal error: output terminal not attached to output net");
        if (outputs[o]->source.first != this || outputs[o]->source.second != o)
            throw ("Internal error: net does not point back to block output terminal");
    }
}

void Module::Net::CheckConsistency() {
    for (list<Terminal>::iterator ti = sinks.begin(); ti != sinks.end(); ++ti)
        if (ti->first->inputs[ti->second] != this)
            throw ("Internal error: block input terminal does not point back to net");
}

void Module::OutputNet::CheckConsistency() {
    Net::CheckConsistency();
    if (!source.first)
        throw ("Internal error: output or internal net has no driver");
    if (source.first && source.first->outputs[source.second] != this)
        throw ("Internal error: block output terminal does not point back to net");
}

void Module::OutputNet::AddFlop(Module *modA, Module *modB, Module *modC) {
    //add flop
    Block *block = new Block(Globals::flop);
    modC->blocks.push_back(block);
    ++modC->numBlocks;
    modC->area += Globals::flop->Size();
    //copy outputnet
    OutputNet *oNet = new OutputNet(maxLength);
    source.first->outputs[source.second] = oNet;
    oNet->source = source;
    for (list<Terminal>::iterator si = sinks.begin(); si != sinks.end(); ++si)
        si->first->inputs[si->second] = oNet;
    oNet->sinks.splice(oNet->sinks.begin(), sinks);
    //connect to flop input
    block->inputs[0] = oNet;
    oNet->sinks.push_back(Terminal(block, 0));
    //connect this outputnet to flop output
    block->outputs[0] = this;
    source.first = block;
    source.second = 0;
    maxLength = 0;

    //loop over all the inputs, and erase thisOutput from their controllableOutputs
    for (Module *mod = modA; mod; mod = (mod == modA) ? modB : (mod == modB) ? modC : 0)
        for (list<InputNet *>::iterator li = mod->inputs.begin(); li != mod->inputs.end(); ++li)
            (*li)->controllableOutputs.erase(this);
}