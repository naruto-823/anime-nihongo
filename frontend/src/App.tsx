import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Conversation from "./pages/Conversation";
import Grammar from "./pages/Grammar";
import Progress from "./pages/Progress";
import Quiz from "./pages/Quiz";
import Reading from "./pages/Reading";
import Review from "./pages/Review";
import Series from "./pages/Series";
import Today from "./pages/Today";
import Tower from "./pages/Tower";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Today />} />
        <Route path="series" element={<Series />} />
        <Route path="episodes/:id/reading" element={<Reading />} />
        <Route path="episodes/:id/conversation" element={<Conversation />} />
        <Route path="review" element={<Review />} />
        <Route path="grammar" element={<Grammar />} />
        <Route path="progress" element={<Progress />} />
        <Route path="tower" element={<Tower />} />
        <Route path="quiz" element={<Quiz />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  );
}
