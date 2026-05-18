// argread.h generated from argread.arf by arf2cc.pl on Sun Feb 26 16:01:12 2023

#ifndef _H_ArgRead
#define _H_ArgRead

#include <string>
#include <cstring>
#include <list>
#include <iostream>
#include <strstream>
#include <fstream>
#include <cstdio>
#include <cstdlib>
#include <climits>
#include <cmath>

#ifdef __hpux
#include "/usr/include/regex.h" //for hpux
#else

#include <regex.h> //for linux and sunos

#endif

using namespace std;

typedef char *charPtr;

class ArgRead {
public:
    ArgRead() : compiledEx(0) {}

    ArgRead(int argc, char *argv[]) : compiledEx(0) { AR_ReadArgs(argc, argv); }

    ~ArgRead();

    void AR_ReadArgs(int argc, char *argv[]);

    void AR_OptionsAndArguments(istream &args, int &argCounter);

    void AR_Usage();

    //Arguments
    string gnlFile;

    //Options
    bool allowLongPaths;
    int minimumInputs;
    float maxFracError;
    int seed;
    bool twoPointNets;
    int minSeqBlocks;
    bool noWarnings;
    float flopCutOff;
    list<string> outputMacrocellFormats;
    int correctionThreshold;
    float maxPinError;
    int minimumOutputs;
    float localConnectionCutOff;
    float correctionBucketFactor;
    bool noLocalConnections;
    bool combineAccordingToSize;
    bool areaAsWeight;
    float meanGCorrectionFactor;
    float minPathLength;
    list<string> outputFormats;
    float flopInsertProbability;
    bool allowLoops;
    float maxPathLength;
    float pathLengthCutOff;
    string logFileName;
    int debugBits;
    bool debugBits_set;
    float minSigmaTFactor;
    bool showProgress;
    bool writeAllModules;
    list<float> delayShapeDistribution;
    bool verboseMode;
    float meanTCorrectionFactor;
    bool dontInsertFlops;
    string ar_commandLine;

private:
    enum RangeCheck {
        none, lower, upper, both
    };

    void AR_ReadFile(int &argCounter);

    void AR_ReadFloat(float &flt, RangeCheck check, float min, float max, bool noErrors = 0);

    void AR_ReadMultipleFloat(list<float> &lst, RangeCheck check, float min, float max);

    void AR_ReadInt(int &i, RangeCheck check, int min, int max, bool noErrors = 0);

    void AR_ReadMultipleInt(list<int> &lst, RangeCheck check, int min, int max);

    void AR_ReadString(string &str, RangeCheck check, int min, int max, bool noErrors = 0);

    void AR_ReadMultipleString(list<string> &lst, RangeCheck check, int min, int max);

    void AR_ReadRegEx(string &str, char *regEx, bool noErrors = 0);

    void AR_ReadMultipleRegEx(list<string> &lst, char *regEx);

    void AR_ReadBool(bool &bl, bool noErrors = 0);

    void AR_ReadMultipleBool(list<bool> &lst);

    void AR_ReadOption(int num, int &argCounter);

    void AR_ReadArgument(int &argCounter);

    int ar_numArguments;
    int ar_numRequired;
    int ar_numOptions;
    char **ar_options;
    char **ar_longOptions;
    bool compiledEx;
    regex_t floatEx;
    regex_t intEx;

    class AR_Argument {
    public:
        AR_Argument() : putBack(0) {}

        void SetStream(istream &in);

        istream *GetStreamPtr();

        bool NewArgument();

        void PutBack();

        bool operator++(int);

        bool operator+=(int a);

        bool operator()();

        const char *SubArg();

        void PrintPosition();

        unsigned int pos;
        string fileName;
    private:
        istream *stream;
        string arg;
        bool putBack;
    } ar_argument;
};

extern ArgRead argRead;

#endif