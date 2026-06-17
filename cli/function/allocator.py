# --- IMPORT ---
import random
import pandas as pd

# --- CONFIG ---
SLOTS_PER_DAY = 4
NUM_HALLS = 1
CAPACITY_PER_SLOT = 500
FIRST_SLOT_HOUR = 7
EXAM_DURATION_HRS = 2
BREAK_DURATION_HRS = 0

# --- HELPERS ---
def format_hour(hour):
    h = int(hour)
    m = int((hour - h) * 60)
    suffix = "AM" if h < 12 else "PM"
    h = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
    return f"{h}:{m:02d} {suffix}"

# --- COMBINATION LOGIC ---
def generate_combination_slots():
    combination_slots = []

    for slot in range(SLOTS_PER_DAY):
        start_hour = FIRST_SLOT_HOUR + slot * (EXAM_DURATION_HRS + BREAK_DURATION_HRS)
        #print(f"Slot {slot + 1}: {format_hour(start_hour)} - {format_hour(end_hour)}")

        for hall in range(NUM_HALLS):
            #print(f"  Hall {hall + 1}: Capacity {CAPACITY_PER_SLOT}")
            combination_slots.append((f"{format_hour(start_hour)}", f"Hall {hall + 1}"))

    return combination_slots


# --- CORE LOGIC ---
def allocate_combinations(data, combination_pool):
    for _, group in data.groupby('ExamDate'):
        if len(group) > len(combination_pool):
            print(f"  Warning: Not enough slots for {len(group)} students! Only {len(combination_pool)} slots available.")
            continue

        random.shuffle(combination_pool)
        daily_pool = combination_pool[:len(group)]

        data.loc[group.index, 'ExamTime'] = [slot[0] for slot in daily_pool]
        data.loc[group.index, 'AssignedHall'] = [slot[1] for slot in daily_pool]
    return data

def assign_numbers(data):
    data = data.sort_values(['ExamDate', 'ExamTime', 'AssignedHall', 'Name'])
    data['Number'] = data.groupby(['ExamDate', 'ExamTime', 'AssignedHall']).cumcount() + 1
    return data


# --- MAIN ---
if __name__ == "__main__":
    from read_data import load_data
    data = load_data('./data/main_data.xlsx')
    combination_pool = generate_combination_slots() * CAPACITY_PER_SLOT
    allocated_data = allocate_combinations(data, combination_pool)
    allocated_data = assign_numbers(allocated_data)
    print(allocated_data.head())
    allocated_data.to_excel('./data/allocated_exam_schedule.xlsx', index=False)