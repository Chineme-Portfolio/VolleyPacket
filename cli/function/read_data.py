# --- IMPORT ---
import pandas as pd

def load_data(file_path):
    data_frame = pd.read_excel(file_path)

    # Normalize columns: strip whitespace, lowercase for matching
    data_frame.columns = data_frame.columns.str.strip()
    col_map = {col: col.lower() for col in data_frame.columns}
    data_frame = data_frame.rename(columns=col_map)

    # Map all known variants to canonical names
    canonical = {
        'name': 'Name', 'names': 'Name',
        'examination number': 'ExamNo', 'exam number': 'ExamNo', 'examno': 'ExamNo',
        'photo link': 'PhotoLink', 'photolink': 'PhotoLink',
        'examination date': 'ExamDate', 'examdate': 'ExamDate',
        'email address': 'Email', 'email': 'Email',
        'phone number': 'PhoneNumber', 'phonenumber': 'PhoneNumber',
    }
    data_frame = data_frame.rename(columns={
        col: canonical[col] for col in data_frame.columns if col in canonical
    })

    data_frame = data_frame.fillna('')
    data_frame['ExamDate'] = pd.to_datetime(data_frame['ExamDate'])
    return data_frame

if __name__ == "__main__":
    file_path = './data/main_data.xlsx'
    data = load_data(file_path)
    print(data.head())