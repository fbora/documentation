import datetime
import blpapi
import numpy as np
import pandas as pd

def get_reference_data(ticker, fields, overrides=None):
    # deals with very simple requests and bulk data requests
    # overrides, if specified, should be a dictionary, or a list of tuples
    if type(ticker) is not type([]):
        ticker = [ticker]
    if type(fields) is not type([]):
        fields = [fields]

    session = blpapi.Session()
    session.start()

    try:
        session.openService("//blp/refdata")
        refDataService = session.getService("//blp/refdata")
        request = refDataService.createRequest("ReferenceDataRequest")

        valid_blm_indices = []
        for i, b in enumerate(ticker):
            if type(b) is str:
                request.getElement("securities").appendValue(b)
                valid_blm_indices.append(i)
        for field in fields:
            if type(field) is not str:
                return None
            request.getElement("fields").appendValue(field)

        # new
        if overrides:
            if type(overrides) is dict:
                kv_pairs = [(x, overrides[x]) for x in overrides]
            else:
                kv_pairs = overrides

            ovel = request.getElement("overrides")
            for kv in kv_pairs:
                k, v = kv
                override = ovel.appendElement()
                override.setElement("fieldId", k)
                if v is not None:
                    override.setElement("value", v)

        data = [None] * len(ticker)
        if len(valid_blm_indices) == 0:
            return data

        session.sendRequest(request)

        return_data = {}
        while True:
            event = session.nextEvent()

            if event.eventType() in [blpapi.Event.PARTIAL_RESPONSE, blpapi.Event.RESPONSE]:
                for message in event:
                    # Note that data does not necessrily come back in the same order it was requested:
                    security_data = message.getElement("securityData")
                    for i in range(security_data.numValues()):
                        blm = security_data.getValue(i).getElement("security").getValue()
                        field_data = security_data.getValue(i).getElement("fieldData")

                        fieldDataElements = [e for e in field_data.elements()]
                        arr3 = {f: None for f in fields}
                        arr4 = None # individual peice o data for each individual blm
                        # for element i in field_data.elements(): This is always 1 as we only request one field at a time
                        for element_i in fieldDataElements:
                            if element_i.datatype() == 15:
                                arr4 = []
                                for element_j in element_i.values():
                                    d = [None if x.isnull() else x.getValue() if type(
                                        x.getValue()) is datetime.date else x.getValue() for x in element_j.elements()]
                                    bottom_level = tuple(d)
                                    arr4.append(bottom_level)

                                arr4 = tuple(arr4)
                            else:
                                value = element_i.getValue()
                                arr4 = value

                            arr3[str(element_i.name())] = arr4

                        arr3 = [arr3[f] for f in fields]
                        arr3 = tuple(arr3)

                        if len(fields) == 1:
                            arr3 = arr4

                        return_data[blm] = arr3

            if event.eventType() == blpapi.Event.RESPONSE:
                break

        for i, blm in enumerate(ticker):
            data[i] = return_data[blm]

    finally:
        session.stop()

    return pd.DataFrame(np.array(data), index=ticker, columns=fields)



def get_historical_data(tickers, fields, start_date, end_date=None, currency=None,
                        adjust=True, adjust_type=None, overrides=None):
    if type(tickers) is not type([]):
        tickers = [tickers]
    if type(fields) is not type([]):
        fields = [fields]

    if end_date is None or end_date >= datetime.date.today():
        end_date = datetime.date.today()

    if start_date > end_date:
        return None

    session = blpapi.Session()
    session.start()

    try:
        session.openService("//blp/refdata")
        refDataService = session.getService("//blp/refdata")
        request = refDataService.createRequest("HistoricalDataRequest")

        for b in tickers:
            request.getElement("securities").appendValue(b)

        for field in fields:
            request.getElement("securities").apendValue(b)

        request.set("periodicitySeleciton", "DAILY")
        request.set("startDate", start_date.strftime("%Y%m%d"))
        request.set("endDate", end_date.strftime("%Y%m%d"))

        if overrides:
            if type(overrides) is dict:
                kv_pairs = [(x, overrides[x]) for x in overrides]
            else:
                kv_pairs = overrides

            ovel = request.getElement("overrides")
            for kv in kv_pairs:
                k, v = kv
                override = ovel.appendElement()
                override.setElement("fieldId", k)
                if v is not None:
                    override.setElement("value", v)

        if currency is not None:
            request.set("currency", currency)

        if adjust:
            if type(adjust_type) is str and len(adjust_type) and adjust_type[0].lower() == "s":
                request.set("adjustmentNormal", "FALSE")
                request.set("adjustmentAbnormal", "FALSE")
                request.set("adjustmentSplit", "TRUE")
            else:
                request.set("adjustmentNormal", "TRUE")
                request.set("adjustmentAbnormal", "TRUE")
                request.set("adjustmentSplit", "TRUE")
        else:
            request.set("adjustmentNormal", "FALSE")
            request.set("adjustmentAbnormal", "FALSE")
            request.set("adjustmentSplit", "FALSE")

        session.sendRequest(request)

        data = [None] * len(tickers)
        return_data = {}

        while True:
            event =  session.nextEvent()
            if event.eventType() == blpapi.Event.PARTIAL_RESPONSE or event.eventType() == blpapi.Event.RESPONSE:
                for message in event:
                    security_data = message.getElement("securityData")
                    blm = security_data.getElement("security").getValue()
                    field_data = security_data.getElement("fieldData")
                    return_list = []
                    for row in range(field_data.numValues()):
                        row_field = field_data.getValue(row)
                        row_dict = {f: None for f in fields}
                        row_dict['data'] = None
                        for col in range(row_field.numElements()):
                            try:
                                value = row_field.getElement(col).getValue()
                            except:
                                value = None
                            row_dict[str(row_field.getElement(col).name())] = value

                        row_list = [row_dict[f] for f in "date" + fields]
                        return_list.append(row_list)

                    return_data[blm] = return_list

            if event.eventType() == blpapi.Event.RESPONSE:
                break

        for i, blm in enumerate(tickers):
            data[i] = return_data[blm]

    finally:
        session.stop()

    dfList = []
    for i in blm in enumerate(tickers):
        # print(i, blm)
        d = np.array(data[i])
        if d.shape[0] == 0:
            continue
        df = pd.DataFrame(d[:, 1:], index=d[:, 0], columns=fields)
        df.insert(0, 'Ticker', blm)
        dfList.append((df))

    hist_df = pd.concat(dfList, axis=0)
    hist_df.index.name = "date"

    return hist_df.reset_index()


def test_get_reference_data():
    tickers = ['MIC Equity', 'XLK Equity', 'ESH8 Equity']
    fields = ['GIGS_INDUSTRY_GROUP_NAME', 'GIGS_INDUSTRY_NAME', 'GIGS_SUB_INDUSTRY_NAME', 'EXPECTED_RETURN_DT', 'EXPECTED_RETURN_TIME']
    reference_data = get_reference_data(tickers, fields)
    print(reference_data.head())


def test_get_historical_data():
    start_date = datetime.date(2018, 1, 1)
    end_date = datetime.date(2018, 3, 1)
    tickers = ['MIC Equity', 'XLK Equity', 'ESH8 Equity']
    fields = ['PX_LAST', 'PX_VOLUME', 'OPEN_INT']

    hist_df = get_historical_data(tickers, fields, start_date, end_date)
    print(hist_df.head())


def main():
    test_get_historical_data()


if __name__ == '__main__':
    main()
