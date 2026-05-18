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

//#define __STL_USE_PVALLOC
//#define __STL_DEBUG

//see pvtools.h for remarks

#include "pvtools.h"

#include <cerrno>
#include <cstdlib>
#include <ctime>
#include <sys/stat.h>
#include <cmath>
#include <iomanip>
#include <strings.h>


Log lerr(1);
Log lout(0);
Log dout(0);
TempDir tempdir;

Log::Log(bool isError) : dest(std), filePtr(0) {
    stdPtr = isError ? &cerr : &cout;
}

Log::~Log() {
    delete filePtr;
}

void Log::SetLogFileAndVerbosity(string &fileName, const char *defaultFile, bool verbose) {
    if (fileName.empty()) {
        char *logDir = getenv("PVLOGS");
        if (logDir)
            fileName = string(logDir) + "/" + defaultFile;
    }
    if (!fileName.empty()) {
        lerr.SetLogFile(fileName.c_str(), both);
        if (verbose)
            SetLogFile(fileName.c_str(), both);
        else
            SetLogFile(fileName.c_str());
    } else {
        if (!verbose)
            SetDestination(none);
    }
}

void Log::SetLogFile(const char *name, Destination d, ios::openmode m) {
    //remove previous filePtr
    delete filePtr;
    filePtr = 0;
    dest = std;

    if (name) {
        if (!(filePtr = new ofstream(name, m))) {
            cerr << "Can't open log file " << name << "\n";
            throw (-1);
        }
        dest = d;
    }
}

void Log::SetDestination(Destination d) {
    dest = d;
}

Log &Log::operator<<(const char *a) {
    if (dest == std || dest == both)
        (*stdPtr) << a << flush;
    if (filePtr && (dest == file || dest == both))
        (*filePtr) << a << flush;
    return *this;
}

Log &Log::operator<<(ostream &(*f)(ostream &a)) {
    if (dest == std || dest == both)
        (*stdPtr) << f << flush;
    if (filePtr && (dest == file || dest == both))
        (*filePtr) << f << flush;
    return *this;
}

ostream &time(ostream &s) {
    long int t = time(0); // for linux and sunos
    string str(ctime(&t));
    s << str.substr(0, str.length() - 1);
    return s;
}

TempDir::~TempDir() {
    if (name.size()) {
        if (keep_it)
            lout << "Temporary directory " << name << " not removed\n";
        else {
            system((string("rm -rf ") + name).c_str());
            lout << "Temporary directory " << name << " removed\n";
        }
    }
}

void TempDir::MakeDir(const char *n) {
    if (n) {
        if (mkdir(n, 0755))
            if (errno != EEXIST) {
                lerr << "Can't create temporary directory " << n << "\n";
                throw (-1);
            } else
                system((string("rm -rf ") + n + "/*").c_str());
        name = n;
        keep_it = 1;
    } else {
        for (int i = 0; i < 10000; ++i) {
            srand((unsigned int) time(0));
            string n = stringPrintf("_tmp%.4u", rand() % 10000);
            if (!mkdir(n.c_str(), 0755)) {
                name = n;
                break;
            }
            if (errno != EEXIST)
                break;
        }
        if (name.empty()) {
            lerr << "Can't create temporary directory\n";
            throw (-1);
        }
    }
    lout << "Temporary directory " << name << " created\n";
}

void TempDir::KeepDir() {
    keep_it = 1;
}

const string &TempDir::Name() const {
    return name;
}

ostream &operator<<(ostream &s, const TempDir &t) {
    s << t.Name();
    return s;
}

int randomNumber(int mod) {
    return int(1.0 * mod * rand() / (RAND_MAX + 1.0));
}

int randomNumber(int min, int max) {
    return int(1.0 * (max - min) * rand() / (RAND_MAX + 1.0)) + min;
}

string stringPrintf(const char *format ...) {
    va_list args;
    va_start(args, format);
    int n = vsnprintf(0, 0, format, args); // TODO used to be: vsprintf(buf, format, (_IO_va_list) args);
    va_end(args);
    char *buf = new char[n + 1];
    va_start(args, format);
    vsprintf(buf, format, args); // TODO used to be: vsprintf(buf, format, (_IO_va_list) args);
    va_end(args);
    string s(buf);
    delete[] buf;
    return s;
}

//string stringVPrintf(const char *format, va_list args) {
//    va_list args2 = args;
//    int n = vsnprintf(0, 0, format, (_IO_va_list)args);
//    char *buf = new char[n + 1];
//    vsprintf(buf, format, (_IO_va_list)args2);
//    string s(buf);
//    delete[] buf;
//    return s;
//}

LineParser::LineParser(const char *filename, const char *commentPrefix, const char *continuationSuffix,
                       bool skipWhiteLines) : in(filename),
                                              currentFilename(filename), prefix(commentPrefix),
                                              suffix(continuationSuffix), skipWhite(skipWhiteLines), lineNumber(0) {
    if (!in)
        throw (string("File error: can't open file ") + filename + " for reading");
    if (int error = regcomp(&whitespaceExpr, "^[[:space:]]*$", REG_EXTENDED))
        throw (stringPrintf("Internal error: while compiling regular expression 1: error %d", error));
    if (int error = regcomp(&sectionExpr, "^[[:space:]]*\\[([[:alnum:][:space:]]+)][[:space:]]*$", REG_EXTENDED)) {
        regfree(&whitespaceExpr);
        throw (stringPrintf("Internal error: while compiling regular expression 2: error %d", error));
    }
    if (int error = regcomp(&keyValuePairExpr, "^[[:space:]]*([[:alnum:]]+)[[:space:]]*=[[:space:]]*(.*)$",
                            REG_EXTENDED)) {
        regfree(&whitespaceExpr);
        regfree(&sectionExpr);
        throw (stringPrintf("Internal error: while compiling regular expression 3: error %d", error));
    }
    if (int error = regcomp(&wordExpr, "^[[:space:]]*([[:alnum:][:punct:]]+)([[:space:]]*)", REG_EXTENDED)) {
        regfree(&whitespaceExpr);
        regfree(&sectionExpr);
        regfree(&keyValuePairExpr);
        throw (stringPrintf("Internal error: while compiling regular expression 4: error %d", error));
    }
}

LineParser::~LineParser() {
    regfree(&whitespaceExpr);
    regfree(&sectionExpr);
    regfree(&keyValuePairExpr);
    regfree(&wordExpr);
}

bool LineParser::ReadLine(string &line) {
    lastSection.erase();
    if (in.eof())
        return 0;
    getline(in, line);
    ++lineNumber;
    if (prefix.length()) {
        string::size_type comment = line.find(prefix);
        if (comment != string::npos)
            line.erase(comment);
    }
    if (suffix.length()) {
        string::size_type continuation = line.rfind(suffix);
        if (continuation != string::npos &&
            !regexec(&whitespaceExpr, line.substr(continuation + suffix.length()).c_str(), 0, 0, 0)) {
            string next;
            if (!ReadLine(next))
                next.erase();
            line.replace(continuation, string::npos, string(" ") + next);
        }
    }
    if (skipWhite && !regexec(&whitespaceExpr, line.c_str(), 0, 0, 0))
        return ReadLine(line);
    return 1;
}

void LineParser::SplitIntoWords(string &line, list<string> &words) {
    words.clear();
    regmatch_t matches[3];
    const char *linePtr = line.c_str();
    while (!regexec(&wordExpr, linePtr, 3, matches, 0)) {
        words.push_back(string(linePtr, matches[1].rm_so, matches[1].rm_eo - matches[1].rm_so));
        linePtr += matches[2].rm_eo;
    }
    if (*linePtr)
        throw ("Internal error: line not empty after splitting");
}

bool LineParser::ReadWords(list<string> &words) {
    words.clear();
    string line;
    bool okay = ReadLine(line);
    if (okay)
        SplitIntoWords(line, words);
    return okay;
}

bool LineParser::IsSection(string &line) {
    regmatch_t matches[2];
    if (!regexec(&sectionExpr, line.c_str(), 2, matches, 0)) {
        lastSection = string(line, matches[1].rm_so, matches[1].rm_eo - matches[1].rm_so);
        return 1;
    } else
        return 0;
}

bool LineParser::ReadSectionLine(string &line) {
    if (ReadLine(line))
        return !IsSection(line);
    else
        return 0;
}

bool LineParser::ReadKey(string &key, string &value) {
    string line;
    if (ReadSectionLine(line)) {
        regmatch_t matches[3];
        if (!regexec(&keyValuePairExpr, line.c_str(), 3, matches, 0)) {
            key = string(line, matches[1].rm_so, matches[1].rm_eo - matches[1].rm_so);
            value = string(line, matches[2].rm_so, matches[2].rm_eo - matches[2].rm_so);
            return 1;
        } else
            throw (stringPrintf("Error in file %s: key-value pair expected at line %d", currentFilename.c_str(),
                                lineNumber));
    } else
        return 0;
}

bool LineParser::ReadNextSection(string &line, bool &linesSkipped) {
    linesSkipped = 0;
    if (lastSection.empty()) {
        while (ReadLine(line)) {
            if (IsSection(line))
                break;
            linesSkipped = 1;
        }
    }
    if (lastSection.empty())
        return 0;
    line = lastSection;
    lastSection.erase();
    return 1;
}

bool LineParser::FindSection(const char *section) {
    if (!strcasecmp(lastSection.c_str(), section))
        return 1;
    string line;
    int startLine = lineNumber;
    bool notWrapped = 1;
    while (notWrapped || lineNumber < startLine) {
        if (!ReadLine(line)) {
            if (!notWrapped)
                throw ("Internal error: wrapped twice");
            in.close();
            in.open(currentFilename.c_str());
            lineNumber = 0;
            notWrapped = 0;
            continue;
        }
        if (IsSection(line) && !strcasecmp(lastSection.c_str(), section))
            return 1;
    }
    return 0;
}

int LineParser::LineNumber() {
    return lineNumber;
}

double uniform() {
    return double(rand()) / (RAND_MAX + 1.0);
}

double uniform(double mmin, double mmax) {
    return uniform() * (mmax - mmin) + mmin;
}

double gaussian() {
    //polar form of the Box-Muller transformation -- http://www.taygeta.com/random/gaussian.html
    double x1, x2, w, y1;
    static double y2;
    static bool use_last = 0;
    if (use_last) {
        use_last = 0;
        return y2;
    }
    do {
        x1 = 2.0 * uniform() - 1.0;
        x2 = 2.0 * uniform() - 1.0;
        w = x1 * x1 + x2 * x2;
    } while (w >= 1.0);
    w = sqrt((-2.0 * log(w)) / w);
    y1 = x1 * w;
    y2 = x2 * w;
    use_last = 1;
    return y1;
}

double gaussian(double mean, double sdev) {
    return gaussian() * sdev + mean;
}

LineWriter &LineWriter::operator<<(const char a) {
    switch (a) {
        case ' ':
            Space();
            break;
        case '\n':
            NewLine();
            break;
        default: {
            CheckEOL();
            strstream s;
            s << a;
            pos += s.pcount();
            out << a;
        }
    }
    return *this;
}

LineWriter &LineWriter::operator<<(const char *a) {
    CheckEOL();
    strstream s;
    s << a;
    pos += s.pcount();
    out << a;
    return *this;
}

LineWriter &LineWriter::operator<<(ostream &(*f)(ostream &a)) {
    CheckEOL();
    strstream s;
    s << f;
    pos += s.pcount();
    out << f;
    return *this;
}

void LineWriter::Space() {
    pos += 1;
    out << ' ';
}

void LineWriter::NewLine() {
    out << endl;
    pos = 0;
}

void LineWriter::AtomicOn() {
    atomic = 1;
}

void LineWriter::AtomicOff() {
    atomic = 0;
}

void LineWriter::CheckEOL() {
    if (atomic)
        return;
    if (pos > maxPos) {
        out << continuation << endl;
        pos = skip;
        out << setw(skip) << "";
    }
}

string Join(const char *joint, list<string> &words) {
    string j;
    for (list<string>::iterator si = words.begin(); si != words.end(); ++si) {
        if (si != words.begin())
            j += joint;
        j += *si;
    }
    return j;
}

bool FileExists(const char *file) {
    ifstream in(file);
    if (!in)
        return 0;
    in.close();
    return 1;
}

void ExtendFile(string &file, const char *ext) {
    file = file.substr(0, file.rfind(ext));
    file += ext;
}

