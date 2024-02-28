import pandas as pd
import numpy as np
import re
import os

def givedaysMME(pid, date, sample, D):
    ## focus on only pid's prescription
    if pid in set(sample["STUDY_ID"].to_list()):
        pdata=sample[sample["STUDY_ID"]==pid]
    else:
        print("No patient's records")
        return False,float('NaN')
    
    ## earlest date = earlest start date
    earlestDate=min(pdata["START_DATE"])
    ## latest date = latest start date + prescribed period
    latestDate=max(pdata['START_DATE']+pd.to_timedelta(pdata["PRESCRIBE_PERIOD"],'d'))
    
    ## if both dates lay out of reporting period, do not consider to calculate
    if date<=earlestDate or date>latestDate+pd.DateOffset(days=D):
        return False,float('NaN')
    
    ## 90 days window: date-90 to date
    start_date=date-pd.DateOffset(days=D)
    
    column_name=pdata.columns.to_list()
    MME_consumption=0
    days=0
    
    for row in pdata.itertuples():
        ## p = prescribed period
        p=row[column_name.index("PRESCRIBE_PERIOD")+1]
        ## rangeStart = that prescription start date
        rangeStart=row[column_name.index("START_DATE")+1]

        ## Situation 1
        ## this med's start date [prior than] 90days Window starts [prior than] this med's end date
        ## take the overlapping
        if rangeStart+pd.DateOffset(days=p) >= start_date >= rangeStart:
            rate=(rangeStart+pd.DateOffset(days=p)-start_date)/np.timedelta64(1,'D')/float(p)
            MME_consumption+=row[column_name.index("MME_consumption")+1]*rate
                                              
        ## Situation 2
        ## this med's start date [later than] 90days window starts, and this med's end date [prior than] 90days window ends
        ## take all prescribed amounts
        if rangeStart > start_date and date> rangeStart+pd.DateOffset(days=p):
            MME_consumption+=row[column_name.index("MME_consumption")+1]
       
        ## Situation 3
        ## this med's start date [prior than] 90days Window ends [prior than] this med's end date
        ## take the overlapping
        if rangeStart+pd.DateOffset(days=p) >= date >= rangeStart:
            rate=(date-rangeStart)/np.timedelta64(1,'D')/float(p)
            MME_consumption+=row[column_name.index("MME_consumption")+1]*rate
      
    return True, MME_consumption

def tabledaysMME(dataset, date, D):
    date=pd.to_datetime(date)
    pid=set(dataset['STUDY_ID'].to_list())
    resultTable=pd.DataFrame(columns=['STUDY_ID',pd.to_datetime(date).strftime("%Y-%m-%d")+" "+str(D)+'Days_MME (mg)',pd.to_datetime(date).strftime("%Y-%m-%d")+' MME/DAY (mg)'])
    for i in pid:
        flag, mme=givedaysMME(i, date, dataset,D)
        # resultTable=resultTable.append({'STUDY_ID':i, pd.to_datetime(date).strftime("%Y-%m-%d")+" "+str(D)+"Days_MME (mg)":mme,pd.to_datetime(date).strftime("%Y-%m-%d")+" MME/DAY (mg)":mme/float(D)},ignore_index=-True)
        resultTable=pd.concat([resultTable, pd.DataFrame([{'STUDY_ID':i, pd.to_datetime(date).strftime("%Y-%m-%d")+" "+str(D)+"Days_MME (mg)":mme,pd.to_datetime(date).strftime("%Y-%m-%d")+" MME/DAY (mg)":mme/float(D)}])])

    return resultTable

def byMonth(df, date, D):
    ## focus on precriptions with reasonable time period
    df=df[(df['START_DATE']<=date) & ((date-df['START_DATE'])/np.timedelta64(1, 'D')<=D+df['PRESCRIBE_PERIOD'])]
    df=df.sort_values(by=['STUDY_ID','ORDER_DATE'])

    ## tp : TAKEN_PERIOD that how many days we take into calculations
    tp=date.strftime("%Y-%m-%d")+" TAKEN_PERIOD"
    
    ## abnormal taken only describes tablet/capsule
    abnormal_taken=df[df['QUANTITY'].str.split().str.get(1).isin(['tablet','capsule'])]
    
    ## exclude PRESCRIBE_PERIOD>=20 from abnormal
    abnormal_taken=abnormal_taken[abnormal_taken['PRESCRIBE_PERIOD']<20]
    
    ## keep 1. for 10 < PRESCRIBE_PERIOD < 20, tablet/day >=15
    ##      2. for PRESCRBE_PERIOD <=10, tablet/day >=10
    abnormal_taken=abnormal_taken[(([float (i) for i in abnormal_taken["QUANTITY"].str.split().str.get(0)]/abnormal_taken["PRESCRIBE_PERIOD"]>=15) 
                                   & (abnormal_taken["PRESCRIBE_PERIOD"]>10)&(abnormal_taken["PRESCRIBE_PERIOD"]<20))
                                  | (([float (i) for i in abnormal_taken["QUANTITY"].str.split().str.get(0)]/abnormal_taken["PRESCRIBE_PERIOD"]>=10) & (abnormal_taken["PRESCRIBE_PERIOD"]<=10))
                                 ]
    
    ## drop abnormal records
    for row in abnormal_taken.itertuples():
        df=df.drop(row[0])

    
    
    ## if reporting date - this med's start date >90:                      # Situation 1
    ##     TAKEN_PERIOD = 90 - reporting date - (this med's start date + PERISCBE_DATE) 
    
    ## elif reporting date - this med's start date < PRESCRIBE_PERIOD:     # Situation 3
    ##     TAKEN_PERIOD = reporting date - this med's start date
    
    ## elif reporting date - this med's start date >= PRESCRIBE_PERIOD:    # Situation 2
    ##     TAKEN_PERIOD = PRESCRIBE_PERIOD
    df[tp]=np.where(((date-df['START_DATE'])/np.timedelta64(1, 'D')>D), 
                                      (df["START_DATE"]-date)/np.timedelta64(1, 'D')+df["PRESCRIBE_PERIOD"]+D,
                                      np.where((date-df['START_DATE'])/np.timedelta64(1, 'D')<df["PRESCRIBE_PERIOD"],
                                      (date-df["START_DATE"])/np.timedelta64(1, 'D'),
                                      df["PRESCRIBE_PERIOD"]))

    ## calculate MME based on TAKEN_PERIOD/PRESCRIBE_PERIOD
    df[date.strftime("%Y-%m-%d")+" TAKEN_MME"]=np.where(df[tp]==df["PRESCRIBE_PERIOD"],df["MME_consumption"],df["MME_consumption"]*df[tp]/df["PRESCRIBE_PERIOD"])
    

    return df, tabledaysMME(df, date, D)

def getMonthList():
    # pre-year: 2021-10-01 - 2022-10-01
    # target period: 2022-10-01 - 2023-04-01
    # post-year: 2023-04-01 - 2024-04-01
    month_set=['2021-10-01','2022-10-01','2023-04-01','2024-04-01']
    
    monthlist=[]
    sixmonth_list=[] 

    year, month, day=month_set[0].split("-")
    year, month, day= int(year), int(month), int(day)
    maxDate=pd.to_datetime(month_set[3])

    while True:  
        if pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day)) <=maxDate:
            monthlist.append(pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day)).strftime("%Y-%m-%d"))
        else:
            break
            
        if month==12:
            year+=1
            month=1
        else:
            month+=1
    

    sixmonth_list.append(month_set[0])
    year, month, day=month_set[0].split("-")
    year, month, day= int(year), int(month), int(day)
    while True:
        if month+6>12:
            month=month-6
            year+=1
        else: month=month+6

        if pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day))<pd.to_datetime(month_set[1]):
            sixmonth_list.append(str(pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day))).split()[0])   
        else:
            break
                                                                                 
    sixmonth_list.append(month_set[1])
    sixmonth_list.append(month_set[2])

    year, month, day=month_set[2].split("-")
    year, month, day= int(year), int(month), int(day)
    while True:
        if month+6>12:
            month=month-6
            year+=1
        else: month=month+6

        if pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day))<=pd.to_datetime(month_set[3]):
            sixmonth_list.append(str(pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day))).split()[0])   
        else:
            break

    return monthlist, sixmonth_list

# def getMonthlist(startDate, df):
#     monthlist=[]
#     sixmonth_list=[]
#     year_list=[]
#     year, month, day=startDate.split("-")
#     year, month, day= int(year), int(month), int(day)
#     maxDate=max(df["START_DATE"])
#     index=0

#     while True:  
#         if pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day)) <=maxDate:
#             monthlist.append(pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day)).strftime("%Y-%m-%d"))
#             if index%6==0:
#                 sixmonth_list.append(pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day)).strftime("%Y-%m-%d"))
#             if index%12==0:
#                 year_list.append(pd.to_datetime(str(year)+"-"+str(month)+'-'+str(day)).strftime("%Y-%m-%d"))
#         else:
#             year, month, day=monthlist[-1].split("-")
#             year, month, day= int(year), int(month), int(day)
#             if month==12:
#                 monthlist.append(pd.to_datetime(str(year+1)+"-"+str(month+1-12)+'-'+str(day)).strftime("%Y-%m-%d"))
#             else:
#                 monthlist.append(pd.to_datetime(str(year)+"-"+str(month+1)+'-'+str(day)).strftime("%Y-%m-%d"))
            
#             year, month, day=sixmonth_list[-1].split("-")
#             year, month, day= int(year), int(month), int(day)
#             if month+6>12:
#                 sixmonth_list.append(pd.to_datetime(str(year+1)+"-"+str(month+6-12)+'-'+str(day)).strftime("%Y-%m-%d"))
#             else:
#                 sixmonth_list.append(pd.to_datetime(str(year)+"-"+str(month+6)+'-'+str(day)).strftime("%Y-%m-%d"))
#             year, month, day=year_list[-1].split("-")
#             year, month, day= int(year), int(month), int(day)
#             year_list.append(pd.to_datetime(str(year+1)+"-"+str(month)+'-'+str(day)).strftime("%Y-%m-%d"))
#             # year_list.append(maxDate.strftime("%Y-%m-%d"))
#             break
#         if month==12:
#             year+=1
#             month=1
#         else:
#             month+=1
#         index+=1

#     return monthlist, sixmonth_list,year_list
