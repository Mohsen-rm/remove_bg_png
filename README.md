# Remove BG Web App

A simple **Flask**-based web application to remove image backgrounds using the `rembg` library and the U²-Net model.

## Features

* **Web UI Upload**: Easily upload images via a web browser.
* **High-Resolution Processing**: Images are temporarily resized to 1024×1024 for better matting.
* **Alpha Matting**: Accurate background removal with configurable thresholds.
* **Download Result**: Get a transparent PNG output.

## Project Structure

```
remove-bg-webapp/
├── app.py           # Main Flask application
├── requirements.txt # Python dependencies
└── templates/
    └── index.html   # Upload form template
```

## Requirements

* Python 3.8 or higher
* Flask
* rembg
* Pillow (PIL)

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/your-username/remove-bg-webapp.git
   cd remove-bg-webapp
   ```
2. **Create and activate a virtual environment**:

   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

* Open `app.py` and replace the `app.secret_key` value with a secure, random string.
* By default, uploaded files are processed in memory; no files are permanently stored on the server.

## Usage

1. **Run the application**:

   ```bash
   # On Windows:
   set FLASK_APP=app.py
   flask run

   # Or simply:
   python app.py
   ```
2. **Open your browser** and navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000).
3. **Upload** an image and download the result with the background removed.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).
