import { initializeApp } from "firebase/app";
import { getDatabase } from "firebase/database";

// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
    apiKey: "AIzaSyA-CdsRfm7pIXDNQClaco2KWnapFZfOaGs",
    authDomain: "smart-iv-pole-f98ce.firebaseapp.com",
    databaseURL: "https://smart-iv-pole-f98ce-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "smart-iv-pole-f98ce",
    storageBucket: "smart-iv-pole-f98ce.firebasestorage.app",
    messagingSenderId: "786256172976",
    appId: "1:786256172976:web:48e4cf68b51ee6cde0a875",
    measurementId: "G-XJ0C0Q0J3G"
};

const app = initializeApp(firebaseConfig);
export const db = getDatabase(app);
