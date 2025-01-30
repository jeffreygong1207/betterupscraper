from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
import pandas as pd
from datetime import datetime  # For historical tracking
import time

# Set up the WebDriver
driver = webdriver.Chrome()

# Open the LMS course management page
driver.get("https://betterup.docebosaas.com/course/manage")

# Function to log in to the LMS
def login(username, password, driver):
    try:
        username_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "user_email"))
        )
        username_field.send_keys(username)
        print("Email entered successfully.")
    except Exception as e:
        print(f"Failed to enter email: {e}")
    continue_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, "button-primary"))
    )
    continue_button.click()

    # Enter password
    try:
        password_field = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "user_password"))
        )
        password_field.send_keys(password)
        print("Password entered successfully.")
    except Exception as e:
        print(f"Failed to enter password: {e}")
    login_button = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Log in']")
    driver.execute_script("arguments[0].click();", login_button)
    print("Login successful!")

# Function to load existing CSV data and initialize historical tracking
def load_existing_data():
    try:
        # Load the CSV file
        existing_df = pd.read_csv("courses_data.csv")
        
        # Safely initialize "Enrollments" as dictionaries
        if "Enrollments" in existing_df.columns:
            existing_df["Enrollments"] = existing_df["Enrollments"].apply(
                lambda x: {datetime.now().strftime("%Y-%m-%d"): int(x)} if isinstance(x, (int, float)) else eval(x)
            )
        
        # Safely initialize "Completed" as dictionaries
        if "Completed" in existing_df.columns:
            existing_df["Completed"] = existing_df["Completed"].apply(
                lambda x: {datetime.now().strftime("%Y-%m-%d"): int(x)} if isinstance(x, (int, float)) else eval(x)
            )

        print("Existing data loaded successfully.")
    except FileNotFoundError:
        print("No existing CSV found. Starting with an empty dataset.")
        columns = ["Title", "Type", "Creation Date", "Days Since Creation", 
                   "Training Materials", "Enrollments", "Completed"]
        existing_df = pd.DataFrame(columns=columns)
    return existing_df

# Function to update the CSV file with new and historical data
def update_csv_with_historical_data(all_courses, existing_df):
    today = datetime.now().strftime("%Y-%m-%d")
    for course in all_courses:
        title = course["Title"]
        if title in existing_df["Title"].values:
            # Update existing course data
            existing_row = existing_df.loc[existing_df["Title"] == title]
            idx = existing_row.index[0]
            existing_df.at[idx, "Enrollments"][today] = course["Enrollments"]
            existing_df.at[idx, "Completed"][today] = course["Completed"]
        else:
            # Add new course data with historical tracking
            new_row = {
                "Title": course["Title"],
                "Type": course["Type"],
                "Creation Date": course["Creation Date"],
                "Days Since Creation": course["Days Since Creation"],
                "Training Materials": course["Training Materials"],
                "Enrollments": {today: course["Enrollments"]},
                "Completed": {today: course["Completed"]},
            }
            existing_df = existing_df.append(new_row, ignore_index=True)

    # Save the updated DataFrame back to the CSV
    existing_df.to_csv("courses_data.csv", index=False)
    print("CSV updated with historical tracking.")

def scrape():
    # Login to the LMS
    login("denysechan@berkeley.edu", "VSSBerkeley2024", driver)
    
    WebDriverWait(driver, 10).until(
        EC.url_contains("/course/manage")  # Update with the post-login dashboard URL path
    )
    tables = driver.find_elements(By.TAG_NAME, "table")
    course_table = tables[1]
    rows = course_table.find_elements(By.TAG_NAME, "tr")
    all_courses.extend(scrape_current_page(rows, []))

    pagination_table = tables[-1]
    pagination_controls = pagination_table.find_element(By.CLASS_NAME, "paginationControls")

    max_attempts = 50  # Maximum number of attempts to click the next button, prevents infinite loops
    attempts = 0

    while attempts < max_attempts:
        try:
            # Wait for the page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            tables = driver.find_elements(By.TAG_NAME, "table")
            course_table = tables[1]
            rows = course_table.find_elements(By.TAG_NAME, "tr")

            # Extract 'data-id' values
            data_ids = []
            for row in rows:
                data_id = row.get_attribute("data-id")
                if data_id:  # Only append non-empty data-id values
                    data_ids.append(data_id)

            # Scrape the data from the current page
            curr_rows = course_table.find_elements(By.TAG_NAME, "tr")
            all_courses.extend(scrape_current_page(curr_rows, data_ids))

            rows = driver.find_elements(By.CSS_SELECTOR, "tr[_ngcontent-ng-c3445667421]")
            
            pagination_table = tables[-1]
            pagination_controls = pagination_table.find_element(By.CLASS_NAME, "paginationControls")
            div_for_next_button = pagination_controls.find_elements(By.TAG_NAME, 'div')[-1]
            next_button = div_for_next_button.find_element(By.TAG_NAME, 'a')
            
            if 'disabled' in next_button.get_attribute('class'):
                break  # Exit the loop if the next button is disabled
            driver.execute_script("arguments[0].click();", next_button)
            print('Clicked next')
            attempts += 1
        except StaleElementReferenceException:
            print('StaleElementReferenceException, retrying...')
            attempts += 1
        except Exception as e:
            print(f"Error: {e}")
            attempts += 1

    print('Reached end of all pages')
    driver.quit()
    return

# Function to collect course data from the current page
def scrape_current_page(rows, data_ids):
    base_url = "https://betterup.docebosaas.com/course/edit/"
    course_stats = []
    driver2 = webdriver.Chrome()
    driver2.get("https://betterup.docebosaas.com/course/manage")
    login("denysechan@berkeley.edu", "VSSBerkeley2024", driver2)
    for data_id in data_ids:
        full_url = f"{base_url}{data_id};tab=reports"
        print(f"Navigating to: {full_url}")
    
        driver2.get(full_url)
        
        WebDriverWait(driver2, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, 'legacy-wrapper-iframe'))
        )

        try:
            counters = WebDriverWait(driver2, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "span12.player-stats-counter"))
            )
            stats = {
                "Enrollments": counters[0].text if len(counters) > 0 else 0,
                "Completed": counters[5].text if len(counters) > 5 else 0,
            }
            course_stats.append(stats)
        except TimeoutException:
            print("Timed out waiting for the element to load")
        except NoSuchElementException:
            print("Element not found")
        except Exception as e:
            print("An error occurred:", str(e))

    driver2.quit()

    courses = []
    for i, row in enumerate(rows):
        cols = row.find_elements(By.TAG_NAME, "td")
        course_data = {
            "Title": cols[1].text,
            "Type": cols[2].text,
            "Creation Date": cols[3].text,
            "Days Since Creation": cols[4].text,
            "Training Materials": cols[5].text,
            "Enrollments": course_stats[i]["Enrollments"],
            "Completed": course_stats[i]["Completed"],
        }
        courses.append(course_data)

    print("Filled Out Courses:", courses)
    return courses

# List to store all course data
all_courses = []

# Load the existing data
existing_df = load_existing_data()

update_csv_with_historical_data(all_courses, existing_df)

# Scrape the data
scrape()

# Update the CSV with historical tracking
update_csv_with_historical_data(all_courses, existing_df)
