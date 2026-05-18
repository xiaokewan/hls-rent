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

map<string, Library> Globals::libraries;
Librarycell *Globals::flop = 0;
ModuleType *Globals::circuit = 0;
int Globals::progress;
map<string, list<string> > Globals::hierarchy;
string Globals::version = "1.1.1";
DelayDistrib Globals::delays;
vector<double> Globals::targetDelayDistrib;
int Globals::moduleCounter = 0;
list<Globals::PtreeNode> Globals::treeData;


int main(int argc, char *argv[]) {
    try {
        argRead.AR_ReadArgs(argc, argv);
        lout.SetLogFileAndVerbosity(argRead.logFileName, "gnl.log", argRead.verboseMode);

        lout << "\n*** gnl " << Globals::version << " started on " << time << endl;
        lout << "Command line: " << argRead.ar_commandLine << endl;
        if (argRead.debugBits_set) {
            dout.SetLogFile("gnl.debug", Log::file, ios::out);
            lout << "Writing debug data to \"gnl.debug\".\n";
        }

        //do stuff
        if (argRead.outputFormats.empty())
            argRead.outputFormats.push_back("hnl");

        if (argRead.writeAllModules)
            argRead.outputMacrocellFormats = argRead.outputFormats;

        if (argRead.delayShapeDistribution.empty())
            Globals::delays.InitDelta(argRead.maxPathLength);
        else
            Globals::delays.InitShape(argRead.maxPathLength, argRead.delayShapeDistribution);

        srand(argRead.seed);

        ParseGnlFile();

        Globals::circuit->GetInstance();

        delete Globals::circuit;

        lout << "*** gnl " << Globals::version << " ended successfully on " << time << endl;
        return 0;
    }
    catch (int e) {
        return e;
    }
    catch (const char *msg) {
        lerr << msg << "\n\n";
    }
    catch (const string &msg) {
        lerr << msg << "\n\n";
    }
    catch (...) {
        lerr << "Internal error: an error is thrown but not catched!\n";
    }
    lout << "*** gnl " << Globals::version << " ended (with errors) on " << time << endl;
}

void ParseGnlFile() {
    LineParser parser(argRead.gnlFile.c_str());
    lout << "Parsing gnl file " << argRead.gnlFile.c_str() << ".\n";
    string section;
    bool linesSkipped;
    try {
        while (parser.ReadNextSection(section, linesSkipped)) {
            if (linesSkipped)
                throw ("syntax error before section header");
            string key, value;
            if (!strcasecmp(section.c_str(), "library")) {
                string name;
                list<Cell *> cells;
                list<string> words;
                while (parser.ReadKey(key, value)) {
                    parser.SplitIntoWords(value, words);
                    if (words.empty())
                        throw ("value expected");
                    if (!strcasecmp(key.c_str(), "name"))
                        name = words.front();
                    else if (!strcasecmp(key.c_str(), "gate") || !strcasecmp(key.c_str(), "latch")) {
                        if (words.size() < 3)
                            throw ("{gate|latch}=<name> <num inputs> <num outputs> [<area> [<delay>]] expected");
                        list<string>::iterator si = words.begin();
                        int i = atoi((++si)->c_str()), o = atoi((++si)->c_str()), area = 1;
                        if (++si != words.end()) {
                            area = atoi(si->c_str());
                            if (area <= 0)
                                throw ("area <= 0");
                        }
                        double delay = 1;
                        if (si != words.end() && ++si != words.end()) {
                            delay = atof(si->c_str());
                            if (delay <= 0)
                                throw ("delay <= 0");
                        }
                        Librarycell *newCell = new Librarycell(words.front(), i, o, !strcasecmp(key.c_str(), "latch"),
                                                               area, delay);
                        cells.push_back(newCell);
                        if (!Globals::flop && i == 1 && o == 1 && newCell->Sequential())
                            Globals::flop = newCell;
                    } else
                        throw ("syntax error");
                }
                if (name.empty())
                    throw ("library name not specified");
                if (Globals::libraries.find(name) != Globals::libraries.end())
                    throw ("library name already in use");
                Globals::libraries[name].cells = cells;
            } else if (!strcasecmp(section.c_str(), "circuit") || !strcasecmp(section.c_str(), "module")) {
                ModuleType *modType = new ModuleType;
                ModuleType::Region region;
                int numCells = 0, libCells = 0;
                int regionBound = -1;
                list<string> words;
                while (parser.ReadKey(key, value)) {
                    parser.SplitIntoWords(value, words);
                    if (words.empty())
                        throw ("value expected");
                    if (!strcasecmp(key.c_str(), "name"))
                        modType->name = words.front();
                    else if (!strcasecmp(key.c_str(), "libraries")) {
                        for (list<string>::iterator si = words.begin(); si != words.end(); ++si) {
                            map<string, Library>::iterator mi = Globals::libraries.find(*si);
                            if (mi == Globals::libraries.end())
                                throw ("Unkown library or module: " + (*si));
                            libCells += mi->second.cells.size();
                        }
                        modType->libraries.splice(modType->libraries.end(), words);
                    } else if (!strcasecmp(key.c_str(), "distribution")) {
                        for (list<string>::iterator si = words.begin(); si != words.end(); ++si) {
                            modType->distribution.push_back(atoi(si->c_str()));
                            ++numCells;
                        }
                    } else if (!strcasecmp(key.c_str(), "size")) {
                        if (regionBound >= 1) {
                            modType->regions[regionBound] = region;
                            region = ModuleType::Region();
                        }
                        if (words.empty() || (regionBound = atoi(words.front().c_str())) < 1)
                            throw ("region boundary size expected");
                    } else if (!strcasecmp(key.c_str(), "meanT")) {
                        region.meanT = atof(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "sigmaT")) {
                        region.sigmaT = atof(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "p")) {
                        region.p = atof(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "q")) {
                        region.q = atof(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "meanG")) {
                        region.meanG = atof(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "sigmaG")) {
                        region.sigmaG = atof(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "I")) {
                        modType->numInputs = atoi(words.front().c_str());
                    } else if (!strcasecmp(key.c_str(), "O")) {
                        modType->numOutputs = atoi(words.front().c_str());
                    } else
                        throw ("syntax error");
                }
                if (regionBound >= 1)
                    modType->regions[regionBound] = region;
                if (libCells != numCells)
                    throw ("number of cells in distribution does not match with number of library cells");
                if (modType->regions.empty())
                    throw ("no Rent regions specified");
                modType->CompleteRegions();

                if (!strcasecmp(section.c_str(), "module")) {
                    if (modType->name.empty())
                        throw ("module name not specified");
                    if (Globals::libraries.find(modType->name) != Globals::libraries.end())
                        throw ("module name already in use");
                    Globals::libraries[modType->name].cells.push_back(modType);
                } else {
                    if (modType->name.empty())
                        modType->name = "top";
                    if (Globals::circuit)
                        throw ("circuit already specified in gnl file");
                    Globals::circuit = modType;
                }
            } else
                throw ("unknown section type [" + section + "]");
        }
        if (!Globals::circuit)
            throw ("no circuit specified in gnl file");
    }
    catch (const char *msg) {
        throw (stringPrintf("%s:%d: %s", argRead.gnlFile.c_str(), parser.LineNumber(), msg));
    }
    catch (const string &msg) {
        throw (stringPrintf("%s:%d: %s", argRead.gnlFile.c_str(), parser.LineNumber(), msg.c_str()));
    }
}

