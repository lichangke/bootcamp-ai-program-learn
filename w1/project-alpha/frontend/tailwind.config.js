var config = {
    darkMode: ["class"],
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                card: "hsl(var(--card))",
                "card-foreground": "hsl(var(--card-foreground))",
                primary: "hsl(var(--primary))",
                "primary-foreground": "hsl(var(--primary-foreground))",
                border: "hsl(var(--border))",
            },
            borderRadius: {
                lg: "0.75rem",
                md: "0.5rem",
                sm: "0.375rem",
            },
        },
    },
    plugins: [],
};
export default config;
