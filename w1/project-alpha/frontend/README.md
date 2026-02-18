# Project Alpha Frontend

## Run

```bash
npm install
npm run dev
```

Frontend default URL: `http://localhost:5173`

## Build

```bash
npm run build
```

## Quality Gates

```bash
npm run lint
npm run test:run
npm run e2e
```

## Notes

- API base URL: `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api`)
- Theme switch: light/dark toggle is available in the header and persisted
  in `localStorage` with key `project-alpha-theme`.
