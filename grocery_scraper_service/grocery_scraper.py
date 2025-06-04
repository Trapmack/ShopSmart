# grocery_scraper.py (GitHub Version)

import argparse
import json
import time
from datetime import datetime, timezone
import requests # For making HTTP requests
from bs4 import BeautifulSoup # For parsing HTML
import logging
import os
import subprocess # For running git commands
import shutil # For removing directories

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Placeholder for Actual Scraping Logic ---
def scrape_store_example_com(store_url, products_to_find, store_name_from_config):
    logging.info(f"Attempting to scrape {store_url} for products: {products_to_find} for store: {store_name_from_config}")
    scraped_data = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        for product_name_query in products_to_find:
            search_url = f"{store_url}/search?q={requests.utils.quote(product_name_query)}" # Example search URL
            logging.info(f"Requesting search URL: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            # !!! THIS IS WHERE YOUR CUSTOM HTML PARSING LOGIC GOES !!!
            # The selectors below are EXAMPLES and WILL LIKELY FAIL on real sites.
            product_elements = soup.find_all('div', class_='product-item') # Hypothetical class

            if not product_elements:
                logging.warning(f"No product elements found for '{product_name_query}' at {store_url} with example class 'product-item'")

            for item_element in product_elements:
                try:
                    name_tag = item_element.find('h2', class_='product-name') # Example
                    price_tag = item_element.find('span', class_='product-price') # Example
                    unit_tag = item_element.find('span', class_='product-unit') # Example
                    link_tag = item_element.find('a', class_='product-link') # Example

                    name = name_tag.text.strip() if name_tag else 'N/A'
                    price_str = price_tag.text.strip().replace('$', '').replace(',', '') if price_tag else '0'
                    unit = unit_tag.text.strip() if unit_tag else 'N/A'
                    item_url = link_tag['href'] if link_tag and link_tag.has_attr('href') else search_url
                    if not item_url.startswith('http'):
                        parsed_store_url = requests.utils.urlparse(store_url)
                        base_url = f"{parsed_store_url.scheme}://{parsed_store_url.netloc}"
                        item_url = base_url + item_url if item_url.startswith('/') else base_url + '/' + item_url

                    if product_name_query.lower() in name.lower(): # Basic matching
                        scraped_data.append({
                            "searched_product": product_name_query,
                            "scraped_name": name,
                            "price": float(price_str) if price_str != 'N/A' else 0.0,
                            "unit": unit,
                            "store_name": store_name_from_config,
                            "item_url": item_url,
                            "timestamp_utc": datetime.now(timezone.utc).isoformat()
                        })
                        break # Found one match for this query, move to next
                except Exception as e:
                    logging.error(f"Error parsing an individual item from {store_url} for {product_name_query}: {e}")
            time.sleep(2) # Be respectful
    except requests.exceptions.Timeout:
        logging.error(f"Timeout accessing {store_url} for '{product_name_query}'.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not fetch {store_url}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error scraping {store_url}: {e}")
    return scraped_data

SCRAPER_REGISTRY = {
    "example_store_type_1": scrape_store_example_com,
    # Add more store identifiers and their scraper functions here
    # "some_other_store": scrape_some_other_store_function,
}

def get_scraper_function(store_identifier):
    scraper_fn = SCRAPER_REGISTRY.get(store_identifier)
    if not scraper_fn:
        logging.warning(f"No scraper registered for identifier: {store_identifier}")
    return scraper_fn

def run_git_command(command, cwd=None):
    logging.info(f"Running git command: {' '.join(command)} in {cwd or os.getcwd()}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
        stdout, stderr = process.communicate(timeout=120)
        if process.returncode == 0:
            logging.info(f"Git command stdout:\n{stdout}")
            if stderr: logging.info(f"Git command stderr (info):\n{stderr}")
            return True, stdout
        else:
            logging.error(f"Git command failed (code {process.returncode}).\nStdout:\n{stdout}\nStderr:\n{stderr}")
            return False, stderr
    except subprocess.TimeoutExpired:
        logging.error(f"Git command {' '.join(command)} timed out.")
        # process.kill() # Popen object might not have kill if communicate already happened on timeout
        # stdout, stderr = process.communicate()
        return False, "Git command timed out."
    except Exception as e:
        logging.error(f"Exception running git command {' '.join(command)}: {e}")
        return False, str(e)

def commit_and_push_to_github(repo_url_with_pat, branch, file_path_in_repo, data_to_upload, commit_message, user_name, user_email):
    repo_name = repo_url_with_pat.split('/')[-1].replace('.git', '')
    clone_dir = os.path.join("/tmp", f"scraper_clone_{repo_name}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")

    if os.path.exists(clone_dir):
        logging.info(f"Removing existing clone directory: {clone_dir}")
        try:
            shutil.rmtree(clone_dir)
        except Exception as e:
            logging.error(f"Error removing directory {clone_dir}: {e}")
            # Continue if removal fails, git clone might handle it or fail informatively
    
    logging.info(f"Cloning {repo_url_with_pat} branch {branch} into {clone_dir}")
    success, clone_out = run_git_command(['git', 'clone', '--branch', branch, '--depth', '1', repo_url_with_pat, clone_dir])
    if not success:
        logging.warning(f"Shallow clone failed for branch {branch}. Output: {clone_out}. Attempting full clone.")
        if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
        success, clone_out = run_git_command(['git', 'clone', repo_url_with_pat, clone_dir])
        if not success:
            logging.error(f"Failed to clone repository. Output: {clone_out}")
            return None
        
        # Checkout the specific branch after full clone or create if not exists
        success, _ = run_git_command(['git', 'checkout', branch], cwd=clone_dir)
        if not success:
            logging.info(f"Branch {branch} not found. Creating new branch.")
            success, _ = run_git_command(['git', 'checkout', '-b', branch], cwd=clone_dir)
            if not success:
                logging.error(f"Failed to create and checkout new branch {branch}.")
                if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
                return None
    
    run_git_command(['git', 'config', 'user.name', user_name], cwd=clone_dir)
    run_git_command(['git', 'config', 'user.email', user_email], cwd=clone_dir)

    full_file_path = os.path.join(clone_dir, file_path_in_repo)
    os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
    try:
        with open(full_file_path, 'w') as f:
            json.dump(data_to_upload, f, indent=4)
        logging.info(f"Data written to {full_file_path}")
    except Exception as e:
        logging.error(f"Failed to write data to file {full_file_path}: {e}")
        if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
        return None

    success, _ = run_git_command(['git', 'add', file_path_in_repo], cwd=clone_dir)
    if not success:
        if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
        return None

    status_success, status_output = run_git_command(['git', 'status', '--porcelain'], cwd=clone_dir)
    if not status_success or not status_output.strip():
        logging.info("No changes to commit.")
        public_repo_url = repo_url_with_pat.replace(repo_url_with_pat.split('@')[0] + '@', 'https://')
        github_file_url = f"{public_repo_url.replace('.git', '')}/blob/{branch}/{file_path_in_repo}"
        if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
        return github_file_url

    success, _ = run_git_command(['git', 'commit', '-m', commit_message], cwd=clone_dir)
    if not success:
        if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
        return None

    success, push_output = run_git_command(['git', 'push', 'origin', branch], cwd=clone_dir)
    if not success:
        if "non-fast-forward" in str(push_output).lower(): # Ensure push_output is a string
            logging.warning("Non-fast-forward error during push. Attempting pull and re-push.")
            pull_success, _ = run_git_command(['git', 'pull', 'origin', branch, '--rebase'], cwd=clone_dir) # Try rebase
            if pull_success:
                push_success_retry, _ = run_git_command(['git', 'push', 'origin', branch], cwd=clone_dir)
                if not push_success_retry:
                    logging.error("Re-push after pull also failed.")
                    if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
                    return None
            else:
                logging.error("Pull failed during conflict resolution attempt.")
                if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
                return None
        else:
            if os.path.exists(clone_dir): shutil.rmtree(clone_dir)
            return None

    public_repo_url = repo_url_with_pat.replace(repo_url_with_pat.split('@')[0] + '@', 'https://')
    github_file_url = f"{public_repo_url.replace('.git', '')}/blob/{branch}/{file_path_in_repo}"
    logging.info(f"Data successfully pushed to GitHub: {github_file_url}")

    if os.path.exists(clone_dir):
        try:
            shutil.rmtree(clone_dir)
            logging.info(f"Cleaned up clone directory: {clone_dir}")
        except Exception as e:
            logging.warning(f"Could not remove clone directory {clone_dir}: {e}")
    return github_file_url

def run_scraper_task(location_info, stores_config, products_to_find,
                     github_repo_url, github_pat, github_branch, github_file_path_prefix,
                     git_user_name, git_user_email):
    logging.info(f"Starting scraper task. Location: {location_info}. Stores: {len(stores_config)}. Products: {products_to_find}.")
    all_pricing_data = []

    for store_conf in stores_config:
        store_name = store_conf.get("name", "Unknown Store")
        store_url = store_conf.get("url")
        store_identifier = store_conf.get("identifier")

        if not store_url or not store_identifier:
            logging.warning(f"Skipping store '{store_name}' due to missing URL/identifier: {store_conf}")
            continue

        scraper_function = get_scraper_function(store_identifier)
        if not scraper_function:
            logging.warning(f"No scraper for '{store_name}' (id: '{store_identifier}'). Skipping.")
            continue

        logging.info(f"Scraping '{store_name}' ({store_url}) using '{store_identifier}' for {products_to_find}.")
        try:
            store_data = scraper_function(store_url, products_to_find, store_name)
            if store_data:
                all_pricing_data.extend(store_data)
            else:
                logging.info(f"No data from scraper for '{store_name}'.")
            logging.info(f"Waiting 5s before next store...")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Error scraping store '{store_name}': {e}")

    if not all_pricing_data:
        logging.warning("No pricing data scraped from any store.")
        return None

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    file_name_in_repo = f"{github_file_path_prefix.rstrip('/')}/pricing_data_{timestamp_str}.json"
    commit_message = f"Update pricing data - {timestamp_str}"

    if not github_repo_url.startswith("https://"):
        logging.error("GitHub repository URL must start with https://")
        return None
    
    repo_url_with_pat = github_repo_url.replace("https://", f"https://{github_pat}@")

    github_file_url = commit_and_push_to_github(
        repo_url_with_pat=repo_url_with_pat,
        branch=github_branch,
        file_path_in_repo=file_name_in_repo,
        data_to_upload=all_pricing_data,
        commit_message=commit_message,
        user_name=git_user_name,
        user_email=git_user_email
    )

    if github_file_url:
        logging.info(f"Successfully pushed pricing list to GitHub: {github_file_url}")
        return github_file_url
    else:
        logging.error("Failed to push pricing list to GitHub.")
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scrape grocery store websites and upload pricing data to GitHub.")
    parser.add_argument("--location_json", required=True, help="JSON string of location information")
    parser.add_argument("--stores_config_json", required=True, help="JSON string of stores to scrape")
    parser.add_argument("--products_json", required=True, help="JSON string of product names to find")
    
    parser.add_argument("--github_repo_url", required=True, help="HTTPS URL of the GitHub repository")
    parser.add_argument("--github_pat", required=False, help="GitHub Personal Access Token. Reads from GITHUB_PAT_ENV if not provided.")
    parser.add_argument("--github_branch", required=True, help="GitHub branch to commit to.")
    parser.add_argument("--github_file_path_prefix", required=True, help="Prefix for file path in GitHub repo.")
    parser.add_argument("--git_user_name", required=True, help="Git user name for commits.")
    parser.add_argument("--git_user_email", required=True, help="Git user email for commits.")

    args = parser.parse_args()

    # Prioritize GITHUB_PAT_ENV if --github_pat is not given
    actual_github_pat = args.github_pat if args.github_pat else os.environ.get('GITHUB_PAT_ENV')
    if not actual_github_pat: # GITHUB_PAT_ENV is also acceptable for GitHub Actions
        actual_github_pat = os.environ.get('GH_PAT') # Common alias in GitHub Actions

    if not actual_github_pat:
        logging.critical("GitHub PAT not found. Provide --github_pat or set GITHUB_PAT_ENV/GH_PAT environment variable.")
        exit(1)

    try:
        location_data = json.loads(args.location_json)
        stores_data = json.loads(args.stores_config_json)
        products_data = json.loads(args.products_json)
    except json.JSONDecodeError as e:
        logging.critical(f"Error decoding JSON input: {e}. Check format.")
        exit(1)

    result_github_url = run_scraper_task(
        location_info=location_data,
        stores_config=stores_data,
        products_to_find=products_data,
        github_repo_url=args.github_repo_url,
        github_pat=actual_github_pat,
        github_branch=args.github_branch,
        github_file_path_prefix=args.github_file_path_prefix,
        git_user_name=args.git_user_name,
        git_user_email=args.git_user_email
    )

    if result_github_url:
        print(result_github_url)
        exit(0)
    else:
        print("SCRAPING_TASK_FAILED_GITHUB")
        exit(1)
