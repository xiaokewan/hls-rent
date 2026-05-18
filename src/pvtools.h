/**************************************************************************
***
*** Copyright (c) 1998-2001 Peter Verplaetse
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

//pvtools.h en pvtools.c
//versie 1.10.1 (8/6/01 -- pv)
//
// * log tools: global class Log lout;
//      lout << "blablabla << long << ... << "\n"; -> schrijft log info naar stdout en/of file.
//      lerr << "foutmelding" << int << "\n"; -> schrijft log info naar stderror en/of file.
//      dout << "debug data" << int << "\n"; -> schrijft log info naar stdout en/of file.
//      lout.SetLogFile("naam",destination); -> voert automatisch lout.SetDestination(destination) uit.
//      lout.SetDestination(destination); -> std, file of both
//
// * temp tools: global class TempDir tempdir;
//      tempdir.MakeDir(); -> directory met naam _tmp#### aanmaken
//      tempdir.MakeDir("naam"); directory met gegeven naam aanmaken, voert automatisch tempdir.KeepDir() uit.
//      tempdir.KeepDir(); directory blijft behouden na destructie
//      cout << tempdir.Name() << endl;
//
// * ostream functies
//      cout << time << endl; -> drukt de tijd af
//      cout << tempdir << endl; -> drukt naam van tempdir af
//
// * string functies
//      stringPrint(T &t) -> zet t om in een string via strstream
//      stringPrintf("format",...) -> sprintf, maar returnt een string
//      stringVPrintf(const char *format, va_list args) -> vsprintf, maar returnt een string
//      string Join(const char *joint,list<string> &words)
//
// * random getallen e.d.
//      int randomNumber(int mod) -> returns random number between 0 and mod-1.
//      int randomNumber(int min, int max) -> returns random number between min and max-1.
//      list<T>::iterator randomElementFromList(list<T> &l) -> returns random element from list, or end() when list is empty
//      void randomizeList(list<T> &l); -> randominze the order of a list
//      void srand(unsigned int seed) -> seeds the above random generator functions
//      double uniform() -> returns a uniform random number between 0 and 1
//      double uniform(double mmin, double mmax) -> returns a uniform random number between mmin and mmax
//      double gaussian() -> returns a gaussian random number with mean 0 and standard deviation 1
//      double gaussian(double mean, double sdev) -> returns a gaussian random number with mean mean and standard deviation sdev
//
// * class LineParser (for parsing files line per line)
//
// * class LineWriter (for writing to a file with limited line lengths)
//
// * bool FileExists(const char *file);
//
// * void ExtendFile(string &s,const char *ext);
//
// * class Map (template class to address, add and lookup in a map<string,T>)

#ifndef _H_Tools
#define _H_Tools

#ifdef __hpux
#define _G_NEED_STDARG_H  //make sure stdarg.h gets included when processing <iostream>
#endif

#include <iostream>
#include <fstream>
#include <string>
#include <cstdarg>
#include <strstream>
#include <vector>
#include <map>
#include <list>

#ifdef __hpux
#include "/usr/include/regex.h" //for hpux
#else

#include <regex.h> //for linux and sunos

#endif

using namespace std;

class Log {
public:
    enum Destination {
        none, std, file, both
    };

    Log(bool isError);

    ~Log();

    void SetLogFileAndVerbosity(string &fileName, const char *defaultFile, bool verbose);

    void SetLogFile(const char *name, Destination d = file, ios::openmode m = ios::app);

    void SetDestination(Destination d);

    Log &operator<<(const char *a);

    Log &operator<<(ostream &(*f)(ostream &a));

    template<class T>
    Log &operator<<(const T &a);

private:
    Destination dest;
    ostream *stdPtr;
    ofstream *filePtr;
};

ostream &time(ostream &s);

class TempDir {
public:
    TempDir() : keep_it(0) {}

    ~TempDir();

    void MakeDir(const char *n = 0);

    void KeepDir();

    const string &Name() const;

private:
    bool keep_it;
    string name;
};

ostream &operator<<(ostream &s, const TempDir &t);

template<class T>
Log &Log::operator<<(const T &a) {
    if (dest == std || dest == both)
        (*stdPtr) << a << flush;
    if (filePtr && (dest == file || dest == both))
        (*filePtr) << a << flush;
    return *this;
}

int randomNumber(int mod);

int randomNumber(int min, int max);

extern Log lerr;
extern Log lout;
extern Log dout;
extern TempDir tempdir;

template<class List>
typename List::iterator randomElementFromList(List &l) {
    typename List::iterator it = l.begin();
    for (int i = randomNumber(l.size()); i > 0; --i)
        ++it;
    return it;
}

template<class List>
void randomizeList(List &l) {
    vector<typename List::iterator> position;
    position.reserve(l.size());
    List n;
    position.push_back(n.end());
    while (!l.empty()) {
        position.push_back(n.insert(position[randomNumber(position.size())], l.front()));
        l.pop_front();
    }
    l = n;
}

string stringPrintf(const char *format ...);

string stringVPrintf(const char *format, va_list args);

template<class T>
string stringPrint(T &t) {
    strstream tmp;
    tmp << t << ends;
    return tmp.str();
}

class LineParser {
public:
    LineParser(const char *filename, const char *commentPrefix = "#", const char *continuationSuffix = "\\",
               bool skipWhiteLines = 1);

    ~LineParser();

    bool ReadNextSection(string &line, bool &linesSkipped);

    bool ReadSectionLine(string &line);

    bool ReadKey(string &key, string &value);

    bool FindSection(const char *section);

    bool ReadLine(string &line);

    void SplitIntoWords(string &line, list<string> &words);

    bool ReadWords(list<string> &words);

    int LineNumber();

    void SetCommentPrefix(const char *commentPrefix) { prefix = commentPrefix; }

    void SetContinuationSuffix(const char *continuationSuffix) { suffix = continuationSuffix; }

    void SetSkipWhiteLines(bool skipWhiteLines) { skipWhite = skipWhiteLines; }

private:
    bool IsSection(string &line);

    ifstream in;
    string currentFilename;
    string prefix;
    string suffix;
    bool skipWhite;
    string lastSection;
    int lineNumber;
    regex_t whitespaceExpr;
    regex_t sectionExpr;
    regex_t keyValuePairExpr;
    regex_t wordExpr;
};

double uniform();

double uniform(double mmin, double mmax);

double gaussian();

double gaussian(double mean, double sdev);

class LineWriter {  //write ' ' to invoke Space(); '\n' to invoke NewLine()
public:
    LineWriter(ostream &output, const int lineSize = 124, const int skipSize = 6,
               const char *continuationString = " \\") :
            out(output), skip(skipSize), maxPos(lineSize), pos(0), continuation(continuationString), atomic(0) {}

    LineWriter &operator<<(const char a);

    LineWriter &operator<<(const char *a);

    LineWriter &operator<<(ostream &(*f)(ostream &a));

    template<class T>
    LineWriter &operator<<(const T &a);

    void Space();

    void NewLine();

    void AtomicOn();

    void AtomicOff();

private:
    ostream &out;
    const int skip;
    const int maxPos;
    int pos;
    const string continuation;
    bool atomic;

    void CheckEOL();
};

template<class T>
LineWriter &LineWriter::operator<<(const T &a) {
    CheckEOL();
    strstream s;
    s << a;
    pos += s.pcount();
    out << a;
    return *this;
}

string Join(const char *joint, list<string> &words);

bool FileExists(const char *file);

void ExtendFile(string &s, const char *ext);

//template <class T>
//class Map {
//public:
//    Map(string p, int first=1): prefix(p), firstNumber(first), nextNumber(first) {}
//    map<string,T> &operator()() { return stringMap; }
//    T *New();  //adds an element with index=prefix+number
//    T *New(string &s);  //throws an error if an element with index s already exists
//    T &operator[](string &s);  //creates a new entry if no element with index s exists
//    T *Lookup(string &s); //throws an error if no element with index s exists
//    string &Lookup(T *t); //throws an error if no element with address t exists
//    T *Exists(string &s);
//    void Clear();
//    void Delete(T *t);
//private:
//    map<string,T> stringMap;
//    map<T *,string> ptrMap;
//    string prefix;
//    int firstNumber;
//    int nextNumber;
//};

//template <class T>
//T *Map<T>::New() {
//    string s;
//    do {
//        s=prefix+stringPrintf("%d",nextNumber++);
//    } while(stringMap.find(s)!=stringMap.end());
//    return New(s);
//}

//template <class T>
//T *Map<T>::New(string &s) {
//    if(stringMap.find(s)!=stringMap.end())
//        throw("error: "+s+" already exists in map");
//    T *ptr=&stringMap.insert(pair<string,T>(s,T())).first->second;
//    ptrMap[ptr]=s;
//    return ptr;
//}
//
//template <class T>
//T &Map<T>::operator[](string &s) {
//    map<string,T>::iterator smi =stringMap.find(s);
//    if(smi==stringMap.end()) {
//        smi=stringMap.insert(pair<string,T>(s,T())).first;
//        ptrMap[&smi->second]=s;
//    }
//    return smi->second;
//}
//
//template <class T>
//T *Map<T>::Lookup(string &s) {
//    map<string,T>::iterator smi=stringMap.find(s);
//    if(smi==stringMap.end())
//        throw("error: cannot find "+s+" in map");
//    return &smi->second;
//}
//
//template <class T>
//string &Map<T>::Lookup(T *t) {
//    map<T *,string>::iterator pmi=ptrMap.find(t);
//    if(pmi==ptrMap.end())
//        throw("error: cannot find pointer in map");
//    return pmi->second;
//}
//
//template <class T>
//T *Map<T>::Exists(string &s) {
//    map<string,T>::iterator smi=stringMap.find(s);
//    if(smi==stringMap.end())
//        return 0;
//    return &smi->second;
//}
//
//template <class T>
//void Map<T>::Clear() {
//    stringMap.clear();
//    ptrMap.clear();
//    nextNumber=firstNumber;
//}
//
//template <class T>
//void Map<T>::Delete(T *t) {
//    string s=Lookup(t);
//    ptrMap.erase(t);
//    stringMap.erase(s);
//}

#endif //{_H_Temp}