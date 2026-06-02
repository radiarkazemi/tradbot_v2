//+------------------------------------------------------------------+
//|  ObjectExporter.mq5  — TraderBot v1                              |
//|                                                                   |
//|  Writes to: trader_objects_SYMBOL.txt (one file per symbol)      |
//|  This prevents multiple EAs from overwriting each other.         |
//|                                                                   |
//|  Also reads: trader_commands_SYMBOL.txt for draw commands        |
//+------------------------------------------------------------------+
#property strict
#property description "TraderBot v1 - Object Exporter + Command Executor"

input int  ExportIntervalSec = 2;
input bool UseCommonFolder   = true;

//+------------------------------------------------------------------+
string TypeName(int t)
  {
   if(t == 0)  return("VLINE");
   if(t == 1)  return("HLINE");
   if(t == 2)  return("TREND");
   if(t == 16) return("RECTANGLE");
   if(t == 20) return("RECTANGLE");
   if(t == 17) return("TRIANGLE");
   if(t == 21) return("TRIANGLE");
   if(t == 18) return("ELLIPSE");
   if(t == 22) return("ELLIPSE");
   if(t == 23) return("TEXT");
   return("OTHER_" + IntegerToString(t));
  }

// File names include the symbol so multiple EAs don't conflict
string ObjFile()  { return("trader_objects_"  + Symbol() + ".txt"); }
string CmdFile()  { return("trader_commands_" + Symbol() + ".txt"); }

//+------------------------------------------------------------------+
int OnInit()
  {
   EventSetTimer(ExportIntervalSec);
   ExecuteCommands();
   ExportObjects();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
  {
   ExecuteCommands();
   ExportObjects();
  }

void OnTick()
  {
   static datetime lastTick = 0;
   datetime now = TimeCurrent();
   if(now - lastTick >= ExportIntervalSec)
     {
      ExecuteCommands();
      ExportObjects();
      lastTick = now;
     }
  }

//+------------------------------------------------------------------+
void ExportObjects()
  {
   int total = ObjectsTotal(0, 0, -1);
   string lines = "";
   lines += "SYMBOL:" + Symbol() + "\n";
   lines += "TS:"     + IntegerToString((int)TimeCurrent()) + "\n";
   // Export current candle OHLC so Python can detect line touches
   double candle_open  = iOpen(Symbol(),  PERIOD_CURRENT, 0);
   double candle_high  = iHigh(Symbol(),  PERIOD_CURRENT, 0);
   double candle_low   = iLow(Symbol(),   PERIOD_CURRENT, 0);
   double candle_close = iClose(Symbol(), PERIOD_CURRENT, 0);
   double bid          = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   lines += "CANDLE_O:" + DoubleToString(candle_open,  _Digits) + "\n";
   lines += "CANDLE_H:" + DoubleToString(candle_high,  _Digits) + "\n";
   lines += "CANDLE_L:" + DoubleToString(candle_low,   _Digits) + "\n";
   lines += "CANDLE_C:" + DoubleToString(candle_close, _Digits) + "\n";
   lines += "BID:"      + DoubleToString(bid,           _Digits) + "\n";
   // Current forming candle time (bar 0) — used to detect same-candle draws
   datetime candle_time = iTime(Symbol(), PERIOD_CURRENT, 0);
   lines += "CANDLE_T:" + IntegerToString((int)candle_time) + "\n";
   // Previous CLOSED candle (bar 1) — used for activation detection
   // Only a completed candle can truly confirm a touch
   double prev_high  = iHigh(Symbol(),  PERIOD_CURRENT, 1);
   double prev_low   = iLow(Symbol(),   PERIOD_CURRENT, 1);
   double prev_close = iClose(Symbol(), PERIOD_CURRENT, 1);
   double prev_open  = iOpen(Symbol(),  PERIOD_CURRENT, 1);
   datetime prev_time = iTime(Symbol(), PERIOD_CURRENT, 1);
   lines += "PREV_H:"  + DoubleToString(prev_high,  _Digits) + "\n";
   lines += "PREV_L:"  + DoubleToString(prev_low,   _Digits) + "\n";
   lines += "PREV_C:"  + DoubleToString(prev_close, _Digits) + "\n";
   lines += "PREV_O:"  + DoubleToString(prev_open,  _Digits) + "\n";
   lines += "PREV_T:"  + IntegerToString((int)prev_time)     + "\n";
   lines += "COUNT:"  + IntegerToString(total) + "\n";

   for(int i = 0; i < total; i++)
     {
      string   nm     = ObjectName(0, i, 0, -1);
      int      typ    = (int)ObjectGetInteger(0, nm, OBJPROP_TYPE);
      double   price1 = ObjectGetDouble(0,  nm, OBJPROP_PRICE, 0);
      double   price2 = ObjectGetDouble(0,  nm, OBJPROP_PRICE, 1);
      datetime time1  = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 0);
      datetime time2  = (datetime)ObjectGetInteger(0, nm, OBJPROP_TIME, 1);
      color    clr    = (color)ObjectGetInteger(0, nm, OBJPROP_COLOR);

      string row = "OBJ";
      row += "|NAME:"    + nm;
      row += "|TYPE:"    + TypeName(typ);
      row += "|TYPEID:"  + IntegerToString(typ);
      row += "|PRICE1:"  + DoubleToString(price1, _Digits);
      row += "|PRICE2:"  + DoubleToString(price2, _Digits);
      row += "|TIME1:"   + IntegerToString((int)time1);
      row += "|TIME2:"   + IntegerToString((int)time2);
      row += "|COLOR:"   + IntegerToString((int)clr);
      lines += row + "\n";
     }

   int flags = FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON;
   int fh = FileOpen(ObjFile(), flags);
   if(fh != INVALID_HANDLE)
     {
      FileWriteString(fh, lines);
      FileClose(fh);
      static int writeCount = 0;
      if(writeCount++ % 30 == 0)  // log every 30 writes (~60s)
         Print("ObjectExporter: wrote ", ObjFile(), " (", total, " objects)");
     }
   else
     {
      Print("ObjectExporter: FAILED to write ", ObjFile(), " error=", GetLastError());
     }
  }

//+------------------------------------------------------------------+
void ExecuteCommands()
  {
   int rflags = FILE_READ | FILE_TXT | FILE_ANSI;
   if(UseCommonFolder) rflags |= FILE_COMMON;

   int fh = FileOpen(CmdFile(), rflags);
   if(fh == INVALID_HANDLE) return;

   bool anyDone = false;
   while(!FileIsEnding(fh))
     {
      string line = FileReadString(fh);
      StringTrimLeft(line); StringTrimRight(line);
      if(StringLen(line) < 3) continue;

      string parts[];
      int n = StringSplit(line, '|', parts);
      if(n < 1) continue;
      string cmd = parts[0];

      if(cmd == "DRAW_HLINE" && n >= 5)
        {
         string nm    = parts[1];
         double price = StringToDouble(parts[2]);
         color  clr   = (color)StringToInteger(parts[3]);
         int    width = (int)StringToInteger(parts[4]);
         int    style = (n >= 6) ? (int)StringToInteger(parts[5]) : STYLE_SOLID;
         if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
         ObjectCreate(0, nm, OBJ_HLINE, 0, 0, price);
         ObjectSetInteger(0, nm, OBJPROP_COLOR,      clr);
         ObjectSetInteger(0, nm, OBJPROP_WIDTH,      width);
         ObjectSetInteger(0, nm, OBJPROP_STYLE,      style);
         ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, nm, OBJPROP_BACK,       true);
         anyDone = true;
        }
      // DRAW_RECT|name|time1|price1|time2|price2|color|fill_color|width|style|back
      else if(cmd == "DRAW_RECT" && n >= 7)
        {
         string   nm    = parts[1];
         datetime t1    = (datetime)StringToInteger(parts[2]);
         double   p1    = StringToDouble(parts[3]);
         datetime t2    = (datetime)StringToInteger(parts[4]);
         double   p2    = StringToDouble(parts[5]);
         color    clr   = (color)StringToInteger(parts[6]);
         color    fill  = (n >= 8)  ? (color)StringToInteger(parts[7]) : clr;
         int      width = (n >= 9)  ? (int)StringToInteger(parts[8])   : 1;
         int      style = (n >= 10) ? (int)StringToInteger(parts[9])   : STYLE_SOLID;
         bool     back  = (n >= 11) ? (bool)StringToInteger(parts[10]) : true;
         if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
         if(ObjectCreate(0, nm, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
           {
            ObjectSetInteger(0, nm, OBJPROP_COLOR,      clr);
            ObjectSetInteger(0, nm, OBJPROP_BGCOLOR,    fill);
            ObjectSetInteger(0, nm, OBJPROP_FILL,       true);
            ObjectSetInteger(0, nm, OBJPROP_WIDTH,      width);
            ObjectSetInteger(0, nm, OBJPROP_STYLE,      style);
            ObjectSetInteger(0, nm, OBJPROP_BACK,       back);
            ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, nm, OBJPROP_HIDDEN,     true);
           }
         anyDone = true;
        }
      // DRAW_TEXT|name|time|price|text|color|fontsize
      else if(cmd == "DRAW_TEXT" && n >= 6)
        {
         string   nm    = parts[1];
         datetime t1    = (datetime)StringToInteger(parts[2]);
         double   p1    = StringToDouble(parts[3]);
         string   txt   = parts[4];
         color    clr   = (color)StringToInteger(parts[5]);
         int      fsz   = (n >= 7) ? (int)StringToInteger(parts[6]) : 8;
         if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
         if(ObjectCreate(0, nm, OBJ_TEXT, 0, t1, p1))
           {
            ObjectSetString(0,  nm, OBJPROP_TEXT,      txt);
            ObjectSetInteger(0, nm, OBJPROP_COLOR,     clr);
            ObjectSetInteger(0, nm, OBJPROP_FONTSIZE,  fsz);
            ObjectSetString(0,  nm, OBJPROP_FONT,      "Arial Bold");
            ObjectSetInteger(0, nm, OBJPROP_BACK,      false);
            ObjectSetInteger(0, nm, OBJPROP_SELECTABLE,false);
            ObjectSetInteger(0, nm, OBJPROP_HIDDEN,    true);
           }
         anyDone = true;
        }
      else if(cmd == "DELETE" && n >= 2)
        {
         if(ObjectFind(0, parts[1]) >= 0) ObjectDelete(0, parts[1]);
         anyDone = true;
        }
      else if(cmd == "DELETE_PREFIX" && n >= 2)
        {
         string prefix = parts[1];
         int total = ObjectsTotal(0, 0, -1);
         for(int i = total - 1; i >= 0; i--)
           {
            string nm = ObjectName(0, i, 0, -1);
            if(StringFind(nm, prefix) == 0) ObjectDelete(0, nm);
           }
         anyDone = true;
        }
     }
   FileClose(fh);

   // Clear command file
   int wflags = FILE_WRITE | FILE_TXT | FILE_ANSI;
   if(UseCommonFolder) wflags |= FILE_COMMON;
   int wfh = FileOpen(CmdFile(), wflags);
   if(wfh != INVALID_HANDLE) { FileWriteString(wfh, ""); FileClose(wfh); }

   if(anyDone) ChartRedraw(0);
  }
//+------------------------------------------------------------------+