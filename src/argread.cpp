// argread.cc generated from argread.arf by arf2cc.pl on Sun Feb 26 16:01:12 2023
#include "argread.h"
//#include <cstring>

ArgRead argRead;

ArgRead::~ArgRead() {
    delete[] ar_options;
    delete[] ar_longOptions;
    if (compiledEx) {
        regfree(&floatEx);
        regfree(&intEx);
    }
}

void ArgRead::AR_ReadArgs(int argc, char *argv[]) {
    ar_commandLine = argv[0];
    for (int i = 1; i < argc; ++i)
        ar_commandLine += string(" ") + argv[i];
    ar_numArguments = 1;
    ar_numRequired = 1;
    ar_numOptions = 34;
    ar_options = new charPtr[ar_numOptions];
    ar_longOptions = new charPtr[ar_numOptions];
    ar_options[0] = "wm";
    ar_longOptions[0] = "wm";
    ar_options[1] = "wa";
    ar_longOptions[1] = "wa";
    ar_options[2] = "w";
    ar_longOptions[2] = "w";
    ar_options[3] = "v";
    ar_longOptions[3] = "v";
    ar_options[4] = "sp";
    ar_longOptions[4] = "sp";
    ar_options[5] = "seed";
    ar_longOptions[5] = "seed";
    ar_options[6] = "plc";
    ar_longOptions[6] = "plc";
    ar_options[7] = "nw";
    ar_longOptions[7] = "nw";
    ar_options[8] = "nlc";
    ar_longOptions[8] = "nlc";
    ar_options[9] = "nfi";
    ar_longOptions[9] = "nfi";
    ar_options[10] = "mstf";
    ar_longOptions[10] = "mstf";
    ar_options[11] = "msb";
    ar_longOptions[11] = "msb";
    ar_options[12] = "mpl";
    ar_longOptions[12] = "mpl";
    ar_options[13] = "mipl";
    ar_longOptions[13] = "mipl";
    ar_options[14] = "mino";
    ar_longOptions[14] = "mino";
    ar_options[15] = "mini";
    ar_longOptions[15] = "mini";
    ar_options[16] = "log";
    ar_longOptions[16] = "log";
    ar_options[17] = "lcc";
    ar_longOptions[17] = "lcc";
    ar_options[18] = "iw";
    ar_longOptions[18] = "iw";
    ar_options[19] = "fip";
    ar_longOptions[19] = "fip";
    ar_options[20] = "fic";
    ar_longOptions[20] = "fic";
    ar_options[21] = "f";
    ar_longOptions[21] = "f";
    ar_options[22] = "eg";
    ar_longOptions[22] = "eg";
    ar_options[23] = "eP";
    ar_longOptions[23] = "eP";
    ar_options[24] = "dtc";
    ar_longOptions[24] = "dtc";
    ar_options[25] = "dsd";
    ar_longOptions[25] = "dsd";
    ar_options[26] = "dgc";
    ar_longOptions[26] = "dgc";
    ar_options[27] = "dct";
    ar_longOptions[27] = "dct";
    ar_options[28] = "dbf";
    ar_longOptions[28] = "dbf";
    ar_options[29] = "d";
    ar_longOptions[29] = "d";
    ar_options[30] = "cms";
    ar_longOptions[30] = "cms";
    ar_options[31] = "ap";
    ar_longOptions[31] = "ap";
    ar_options[32] = "al";
    ar_longOptions[32] = "al";
    ar_options[33] = "2p";
    ar_longOptions[33] = "2p";

    //Set defaults:
    allowLongPaths = 0;
    minimumInputs = 1;
    maxFracError = 20;
    seed = 1;
    twoPointNets = 0;
    minSeqBlocks = 0;
    noWarnings = 0;
    flopCutOff = 70;
    correctionThreshold = 2;
    maxPinError = 20;
    minimumOutputs = 1;
    localConnectionCutOff = 80;
    correctionBucketFactor = 1.3;
    noLocalConnections = 0;
    combineAccordingToSize = 0;
    areaAsWeight = 0;
    meanGCorrectionFactor = 0.01;
    minPathLength = 0;
    flopInsertProbability = 0.1;
    allowLoops = 0;
    maxPathLength = 40;
    pathLengthCutOff = 70;
    logFileName = "";
    debugBits = 0;
    debugBits_set = 0;
    minSigmaTFactor = 2.0;
    showProgress = 0;
    writeAllModules = 0;
    verboseMode = 0;
    meanTCorrectionFactor = 0.2;
    dontInsertFlops = 0;
    //Compile regular expressions for float and int
    if (regcomp(&intEx, "^[\\+\\-]{0,1}[0-9]+$", REG_EXTENDED))
        throw ("Cannot compile regular expression for integers");
    if (regcomp(&floatEx, "^[\\+-]{0,1}[0-9]*(\\.[0-9]+){0,1}$", REG_EXTENDED))
        throw ("Cannot compile regular expression for floats");
    compiledEx = 1;

    //Read options/arguments
    strstream arguments;
    for (int i = 1; i < argc; i++)
        arguments << argv[i] << " ";
    int argCounter = 0;
    try {
        AR_OptionsAndArguments(arguments, argCounter);
        if (argCounter < ar_numRequired)
            throw (argCounter);
    }
    catch (int count) {
        cout << "Expected ";
        int expected;
        if (count < ar_numRequired) {
            cout << "at least ";
            expected = ar_numRequired;
        } else {
            cout << "at most ";
            expected = ar_numArguments;
        }
        cout << expected << " argument" << (expected == 1 ? "" : "s") << ", but " << count
             << (count == 1 ? " was" : " were") << " given.\n\n";
        AR_Usage();
        throw (-1);
    }
    catch (char mode) {
        if (mode & 4)
            cout << "Unexpected end of argument list.\n\n";
        if (mode & 1)
            ar_argument.PrintPosition();
        if (mode & 2)
            AR_Usage();
        throw (-1);
    }
}

void ArgRead::AR_OptionsAndArguments(istream &args, int &argCounter) {
    ar_argument.SetStream(args);
    while (ar_argument.NewArgument()) {
        if (*ar_argument.SubArg() == '-') {
            ar_argument++;
            char ***optionList = &ar_options;
            while (ar_argument()) {
                if (*ar_argument.SubArg() == '-') {
                    ar_argument++;
                    optionList = &ar_longOptions;
                }
                int num;
                for (num = 0; num < ar_numOptions; num++) {
                    int len = strlen((*optionList)[num]);
                    if (!strncmp((*optionList)[num], ar_argument.SubArg(), len)) {
                        ar_argument += len;
                        AR_ReadOption(num, argCounter);
                        break;
                    }
                }
                if (num == ar_numOptions) {
                    cout << "Unknown option specified:\n";
                    throw (char(3));
                }
            }
        } else
            AR_ReadArgument(argCounter);
    }
}

void ArgRead::AR_ReadFile(int &argCounter) {
    AR_ReadString(ar_argument.fileName, none, 0, 0);
    ifstream inFile(ar_argument.fileName.c_str());
    if (!inFile) {
        cerr << "Can't open file " << ar_argument.fileName << "\n\n";
        throw (char(0));
    }
    istream *oldStreamPtr = ar_argument.GetStreamPtr();
    AR_OptionsAndArguments(inFile, argCounter);
    ar_argument.SetStream(*oldStreamPtr);
    inFile.close();
}

void ArgRead::AR_ReadFloat(float &flt, RangeCheck check, float min, float max, bool noErrors) {
    int num;
    if (!ar_argument())
        if (!ar_argument.NewArgument())
            throw (char(6));
    if (regexec(&floatEx, ar_argument.SubArg(), 0, 0, 0)) {
        if (!noErrors)
            cout << "This is not a valid floating point value:\n";
        throw (char(3));
    }
    sscanf(ar_argument.SubArg(), "%f%n", &flt, &num);
    if (check == lower && flt < min) {
        if (!noErrors)
            cout << "A value greater than or equal to " << min << " is expected:\n";
        throw (char(3));
    }
    if (check == upper && flt > max) {
        if (!noErrors)
            cout << "A value less than or equal to " << max << " is expected:\n";
        throw (char(3));
    }
    if (check == both && (flt < min || flt > max)) {
        if (!noErrors)
            cout << "A value between " << min << " and " << max << " is expected:\n";
        throw (char(3));
    }
    ar_argument.pos += num;
}

void ArgRead::AR_ReadMultipleFloat(list<float> &lst, RangeCheck check, float min, float max) {
    float tmp;
    try {
        while (1) {
            AR_ReadFloat(tmp, check, min, max, 1);
            lst.push_back(tmp);
        }
    }
    catch (char mode) {
        if (mode < 4)
            ar_argument.PutBack();
    }
}

void ArgRead::AR_ReadInt(int &i, RangeCheck check, int min, int max, bool noErrors) {
    int num;
    if (!ar_argument())
        if (!ar_argument.NewArgument())
            throw (char(6));
    if (regexec(&intEx, ar_argument.SubArg(), 0, 0, 0)) {
        if (!noErrors)
            cout << "This is not a valid integer value:\n";
        throw (char(3));
    }
    sscanf(ar_argument.SubArg(), "%d%n", &i, &num);
    if (check == lower && i < min) {
        if (!noErrors)
            cout << "A value greater than or equal to " << min << " is expected:\n";
        throw (char(3));
    }
    if (check == upper && i > max) {
        if (!noErrors)
            cout << "A value less than or equal to " << max << " is expected:\n";
        throw (char(3));
    }
    if (check == both && (i < min || i > max)) {
        if (!noErrors)
            cout << "A value between " << min << " and " << max << " was expected:\n";
        throw (char(3));
    }
    ar_argument.pos += num;
}

void ArgRead::AR_ReadMultipleInt(list<int> &lst, RangeCheck check, int min, int max) {
    int tmp;
    try {
        while (1) {
            AR_ReadInt(tmp, check, min, max, 1);
            lst.push_back(tmp);
        }
    }
    catch (char mode) {
        if (mode < 4)
            ar_argument.PutBack();
    }
}

void ArgRead::AR_ReadString(string &str, RangeCheck check, int min, int max, bool noErrors) {
    if (!ar_argument())
        if (!ar_argument.NewArgument())
            throw (char(6));
    int len = strlen(ar_argument.SubArg());
    if ((check == lower || check == both) && len < min) {
        if (!noErrors)
            cout << "The string is too short; at least " << min << " character" << (min == 1 ? " was" : "s were")
                 << " expected:\n";
        throw (char(3));
    }
    if ((check == upper || check == both) && len > max) {
        if (!noErrors)
            cout << "The string is too long; at most " << max << " character" << (max == 1 ? " was" : "s were")
                 << " expected:\n";
        throw (char(3));
    }
    str = ar_argument.SubArg();
    ar_argument.pos += len;
}

void ArgRead::AR_ReadMultipleString(list<string> &lst, RangeCheck check, int min, int max) {
    string tmp;
    try {
        while (1) {
            AR_ReadString(tmp, check, min, max, 1);
            lst.push_back(tmp);
        }
    }
    catch (char mode) {
        if (mode < 4)
            ar_argument.PutBack();
    }
}

void ArgRead::AR_ReadRegEx(string &str, char *regEx, bool noErrors) {
    string uncompiledEx("^(");
    uncompiledEx = uncompiledEx + regEx + ")$";
    regex_t compEx;
    if (regcomp(&compEx, uncompiledEx.c_str(), REG_EXTENDED)) {
        cerr << "Regular expression " << regEx << " cannot be compiled!\n";
        throw (uncompiledEx);
    }
    if (!ar_argument())
        if (!ar_argument.NewArgument())
            throw (char(6));
    if (regexec(&compEx, ar_argument.SubArg(), 0, 0, 0)) {
        if (!noErrors)
            cout << "This string does not match the regular expression /" << regEx << "/:\n";
        regfree(&compEx);
        throw (char(3));
    }
    str = ar_argument.SubArg();
    ar_argument.pos += strlen(ar_argument.SubArg());
    regfree(&compEx);
}

void ArgRead::AR_ReadMultipleRegEx(list<string> &lst, char *regEx) {
    string tmp;
    try {
        while (1) {
            AR_ReadRegEx(tmp, regEx, 1);
            lst.push_back(tmp);
        }
    }
    catch (char mode) {
        if (mode < 4)
            ar_argument.PutBack();
    }
}

void ArgRead::AR_ReadBool(bool &bl, bool noErrors) {
    char c;
    if (!ar_argument())
        if (!ar_argument.NewArgument())
            throw (char(6));
    sscanf(ar_argument.SubArg(), "%c", &c);
    if (c < '0' || c > '1') {
        if (!noErrors)
            cout << "A boolean value (0 or 1) was expected:\n";
        throw (char(3));
    }
    ar_argument.pos++;
    bl = c - '0';
}

void ArgRead::AR_ReadMultipleBool(list<bool> &lst) {
    bool tmp;
    try {
        while (1) {
            AR_ReadBool(tmp, 1);
            lst.push_back(tmp);
        }
    }
    catch (char mode) {
        if (mode < 4)
            ar_argument.PutBack();
    }
}

void ArgRead::AR_Argument::PutBack() {
    putBack = 1;
}

void ArgRead::AR_Argument::SetStream(istream &in) {
    stream = &in;
}

istream *ArgRead::AR_Argument::GetStreamPtr() {
    return stream;
}

bool ArgRead::AR_Argument::NewArgument() {
    if (putBack)
        putBack = 0;
    else {
        arg = "";
        (*stream) >> arg;
        pos = 0;
    }
    return arg.length() > pos;
}

bool ArgRead::AR_Argument::operator++(int) {
    pos++;
    return arg.length() > pos && !putBack;
}

bool ArgRead::AR_Argument::operator+=(int a) {
    pos += a;
    return arg.length() > pos && !putBack;
}

bool ArgRead::AR_Argument::operator()() {
    return arg.length() > pos && !putBack;
}

const char *ArgRead::AR_Argument::SubArg() {
    return &arg.c_str()[pos];
}

void ArgRead::AR_Argument::PrintPosition() {
    cout << "     " << arg << "\n";
    if (pos > 0) {
        cout.width(pos + 7);
        cout << "^\n";
        cout.width(0);
    }
    cout << "\n";
}

void ArgRead::AR_ReadOption(int num, int &argCounter) {
    switch (num) {
        case 4:
            showProgress = 1;
            break;
        case 10:
            AR_ReadFloat(minSigmaTFactor, lower, 0, 0);
            break;
        case 1:
            writeAllModules = 1;
            break;
        case 25:
            AR_ReadMultipleFloat(delayShapeDistribution, lower, 0, 0);
            break;
        case 12:
            AR_ReadFloat(maxPathLength, lower, 0, 0);
            break;
        case 6:
            AR_ReadFloat(pathLengthCutOff, both, 0, 100);
            break;
        case 16:
            AR_ReadString(logFileName, none, 0, 0);
            break;
        case 29:
            AR_ReadInt(debugBits, none, 0, 0);
            debugBits_set = 1;
            break;
        case 3:
            verboseMode = 1;
            break;
        case 24:
            AR_ReadFloat(meanTCorrectionFactor, lower, 0, 0);
            break;
        case 9:
            dontInsertFlops = 1;
            break;
        case 11:
            AR_ReadInt(minSeqBlocks, lower, 0, 0);
            break;
        case 20:
            AR_ReadFloat(flopCutOff, both, 0, 100);
            break;
        case 7:
            noWarnings = 1;
            break;
        case 27:
            AR_ReadInt(correctionThreshold, lower, 1, 0);
            break;
        case 0:
            AR_ReadMultipleRegEx(outputMacrocellFormats, "hnl|netD|netD2|nets|info|plot|rtd|dat|tree|ptree|blif");
            break;
        case 23:
            AR_ReadFloat(maxPinError, both, 0, 100);
            break;
        case 28:
            AR_ReadFloat(correctionBucketFactor, lower, 1, 0);
            break;
        case 17:
            AR_ReadFloat(localConnectionCutOff, both, 0, 100);
            break;
        case 14:
            AR_ReadInt(minimumOutputs, lower, 0, 0);
            break;
        case 31:
            allowLongPaths = 1;
            break;
        case 15:
            AR_ReadInt(minimumInputs, lower, 0, 0);
            break;
        case 22:
            AR_ReadFloat(maxFracError, both, 0, 100);
            break;
        case 5:
            AR_ReadInt(seed, none, 0, 0);
            break;
        case 33:
            twoPointNets = 1;
            break;
        case 21:
            AR_ReadFile(argCounter);
            break;
        case 2:
            AR_ReadMultipleRegEx(outputFormats, "hnl|netD|netD2|nets|info|plot|rtd|dat|tree|ptree|blif");
            break;
        case 19:
            AR_ReadFloat(flopInsertProbability, both, 0, 1);
            break;
        case 32:
            allowLoops = 1;
            break;
        case 8:
            noLocalConnections = 1;
            break;
        case 30:
            combineAccordingToSize = 1;
            break;
        case 18:
            areaAsWeight = 1;
            break;
        case 13:
            AR_ReadFloat(minPathLength, lower, 0, 0);
            break;
        case 26:
            AR_ReadFloat(meanGCorrectionFactor, lower, 0, 0);
            break;
    }
}

void ArgRead::AR_ReadArgument(int &argCounter) {
    if (argCounter >= ar_numArguments)
        throw (++argCounter);
    switch (argCounter) {
        case 0:
            AR_ReadString(gnlFile, none, 0, 0);
            break;
    }
    if (ar_argument()) {
        cout << "Syntax error in argument " << ++argCounter << ":\n";
        throw (char(3));
    }
    argCounter++;
}

void ArgRead::AR_Usage() {
    cout << ""
            "Usage: gnl [options] <XX.gnl>\n"
            "  options: \n"
            "     general options:\n"
            "	f		Options & arguments file\n"
            "	v		Verbose mode on\n"
            "	d <level>	Debug mode on\n"
            "	log <file>	Log filename\n"
            "\n"
            "     generation options:\n"
            "	sp		Show progress\n"
            "	nw		Don't show warnings\n"
            "	eP <%error>	Warn if error on number of pins too big [20]\n"
            "	eg <%error>	Warn if error on final output fraction too big [20]\n"
            "\n"
            "     output options:\n"
            "	w <formats>	Output formats (hnl,netD,netD2,nets,info,plot,rtd,dat,tree,\n"
            "			ptree) [hnl]\n"
            "	wm <formats>	Output formats for internal macrocells\n"
            "	wa		Write output for all modules (-wm identical to -w)\n"
            "\n"
            "     loop and delay parameters:\n"
            "	mpl		Maximum path length [40]\n"
            "	plc		Path length cut-off percentage [70]\n"
            "	dsd		Delay shape distribution [ 0 .. 0 1 ]\n"
            "	msb		Minimum number of blocks for sequential combination [0]\n"
            "	mipl		Minimum path length [0]\n"
            "	ap		Allow long paths\n"
            "	al		Allow combinational loops (this implies -ap)\n"
            "\n"
            "     parameters for improved control:\n"
            "	nlc		Do not allow local connections\n"
            "	lcc		Local connection cut-off percentage [80]\n"
            "	nfi		Do not allow flop insertion\n"
            "	fic		Flop insertion cut-off percentage [70]\n"
            "	fip		Flop insertion cut-off probability [0.1]\n"
            "	dbf <factor>	Distribution correction bucket factor [1.3]\n"
            "	dct <num>	Distribution correction threshold [2]\n"
            "	dtc <fraction>	Distribution mean T correction factor [0.2]\n"
            "	dgc <error>	Distribution mean G correction factor [0.01]\n"
            "	mstf <factor>	Minimum sigmaT factor for combination [2.0]\n"
            "\n"
            "    other parameters:\n"
            "	cms 		Combine modules according to module size\n"
            "	seed <seed>	Initial seed [1]\n"
            "	mini <min in>	Minimum number of intermediate input pins [1]\n"
            "	mino <min out>	Minimum number of intermediate output pins [1]\n"
            "	2p		Allow only internal connections (2-point nets)\n"
            "	iw		Ignore weights while generating\n"
            "";
}
