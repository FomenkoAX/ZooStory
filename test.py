# Configuration
CHEST_SLEEP = True  # Change this to True if you want to allow sleeping
sleep_time = 4340  # in seconds

# Time until the chest appears (example values)
chest_time = 1736886000 - 1736867594  # in seconds

# Logic to determine if we should sleep until the chest appears
if chest_time > 0:
    if chest_time <= sleep_time and CHEST_SLEEP:
        print('chest_time:', chest_time)
        print(f"Sleeping {round(chest_time / 60, 1)} min, Until Chest appears...")
    elif chest_time > sleep_time and CHEST_SLEEP:
        print('Skipped: Chest will appear after sleep time.')
else:
    print("Error: Chest time is not valid (less than or equal to zero).")

print("Done")