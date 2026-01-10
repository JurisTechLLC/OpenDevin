/** @type {import('tailwindcss').Config} */
import { nextui } from "@nextui-org/react";
export default {
 content: [
   "./src/**/*.{js,ts,jsx,tsx}",
   "./node_modules/@nextui-org/theme/dist/**/*.{js,ts,jsx,tsx}",
 ],
 darkMode: "class",
 plugins: [
   nextui({
     defaultTheme: "dark",
     layout: {
       radius: {
         small: "5px",
         large: "20px",
       },
     },
     themes: {
       dark: {
         colors: {
           primary:"#4465DB",
         },
       }
     }
   }),
 ],
};
