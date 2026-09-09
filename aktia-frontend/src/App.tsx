import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Clinic from "./pages/Clinic";
import Radiographs from "./pages/Radiographs";
import RadiographDetail from "./pages/RadiographDetail";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="clinica" element={<Clinic />} />
        <Route path="radiografias" element={<Radiographs />} />
        <Route path="radiografias/:id" element={<RadiographDetail />} />
      </Route>
    </Routes>
  );
}
