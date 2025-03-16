# PDF Extractor Web Interface

A modern web interface for the PDF Transaction Extractor, built with FastAPI and React.

## Features

- Drag-and-drop PDF upload
- Real-time processing status updates
- Transaction data display
- CSV export functionality
- Modern, responsive UI

## Project Structure

```
web/
├── backend/         # FastAPI backend
│   ├── main.py     # Main application file
│   └── requirements.txt
└── frontend/       # React frontend
    ├── src/        # Source code
    ├── public/     # Static files
    └── package.json
```

## Setup Instructions

### Backend Setup

1. Create and activate a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the backend server:
   ```bash
   python main.py
   ```
   The API will be available at http://localhost:8000

### Frontend Setup

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```
   The web interface will be available at http://localhost:5173

## Usage

1. Open the web interface in your browser
2. Drag and drop a PDF bank statement or click to select one
3. Wait for the processing to complete
4. View the extracted transactions
5. Download the results as CSV if needed

## API Endpoints

- `GET /`: Health check endpoint
- `POST /upload/`: Upload and process PDF files
- `WS /ws`: WebSocket endpoint for real-time updates

## Development

- Backend uses FastAPI with async support
- Frontend built with React, TypeScript, and Mantine UI
- Real-time updates via WebSocket
- File upload handling with multipart/form-data 