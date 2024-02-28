import pandas as pd
import numpy as np
import re
import os

import MME
import processData

mapping_list={"codeine":0.15,'fentanyl': 2.4,'hydrocodone':1,'hydromorphone':4,'methadone':{20: 4,40:8, 60:10, 61:12},'morphine':1,
              'oxycodone':1.5,'oxymorphone':3,'tramadol':2.4}

med_list=pd.read_csv("MERLIN_3664_MEDS.csv")
med_list=processData.processMedList(med_list, mapping_list)

meds=meds=pd.read_excel('Prescription_sample.xlsx')
meds['ORDER_DATE']=pd.to_datetime(meds['ORDER_DATE'])
meds['START_DATE']=pd.to_datetime(meds['START_DATE'])
meds['END_DATE']=pd.to_datetime(meds['END_DATE'])

med_prescription=processData.processMedPrescription(meds)

df=processData.processData(med_prescription, med_list, mapping_list)

month_list, sixmonth_list=MME.getMonthList()
# print(month_list)
# print(sixmonth_list)
# print(year_list)


# if there is an end date, PRESCRIBE_PERIOD is the actuall days difference, otherwise 30 it is.
df["PRESCRIBE_PERIOD"]=np.where(pd.isna(df["END_DATE"]), 30, np.where((df["END_DATE"]-df["START_DATE"])/np.timedelta64(1, 'D')>30, 30, (df["END_DATE"]-df["START_DATE"])/np.timedelta64(1, 'D')))    

## for Check tablets/day manually
df['tablets/day']=np.where(df["strength_unit"].isin(['tablet','capsule']),
                        [float (i) for i in df["QUANTITY"].str.split().str.get(0)]/df["PRESCRIBE_PERIOD"],
                        float("NaN"))

# calculate based on given dates list
for D in [90,30]:
    df_=df
    for m in month_list:
        record, result=MME.byMonth(df_,pd.to_datetime(m),D)
        df_=pd.merge(df_,record.loc[:,["MED_ORDER_ID",m+' TAKEN_PERIOD',m+' TAKEN_MME']], on='MED_ORDER_ID',how='left')
        df_=pd.merge(df_,result,on='STUDY_ID',how='left')

    df_.to_excel(str(D)+"Days_MME.xlsx", index=False)
    

