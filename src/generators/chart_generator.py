# src/generators/chart_generator.py
import logging
import asyncio
import json
from pathlib import Path
from pyppeteer import launch
from src import config

async def create_chart_image(chart_data: dict, output_path: Path) -> Path:
    """
    Launches a headless browser (Pyppeteer) to render an HTML/Chart.js
    template and screenshots the resulting chart.
    """
    logging.info("Launching headless browser to generate chart...")
    browser = None
    try:
        browser = await launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.newPage()
        
        # Set a large viewport for a high-quality chart
        await page.setViewport({'width': 1280, 'height': 720})
        
        # 1. Go to the local HTML template file
        template_url = f"file://{config.CHART_TEMPLATE_PATH.absolute()}"
        await page.goto(template_url)

        # 2. Wait for the page (and Chart.js CDN) to be fully loaded
        await page.waitForSelector('#myChart')
        
        # 3. Inject data and render the chart by calling the JS function
        # We must serialize the Python dict to a JSON string
        data_json = json.dumps(chart_data)
        await page.evaluate(f"renderChart({data_json})")
        
        # 4. Wait for the chart animation to (hypothetically) finish
        # Even with 0ms duration, a small delay ensures rendering
        await asyncio.sleep(0.5) 
        
        # 5. Target the chart's container div for a clean screenshot
        chart_element = await page.querySelector('#chartContainer')
        if not chart_element:
            raise RuntimeError("Could not find #chartContainer element in template.")
            
        await chart_element.screenshot({'path': str(output_path)})
        
        logging.info(f"Successfully generated chart image: {output_path}")
        return output_path
        
    except Exception as e:
        logging.error(f"Error during chart generation with Pyppeteer: {e}")
        raise
    finally:
        if browser:
            await browser.close()