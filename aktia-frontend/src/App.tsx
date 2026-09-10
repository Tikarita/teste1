import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import Clinic from "./pages/Clinic";
import Login from "./pages/Login";
import Radiographs from "./pages/Radiographs";
import RadiographDetail from "./pages/RadiographDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="clinica" element={<Clinic />} />
          <Route path="radiografias" element={<Radiographs />} />
          <Route path="radiografias/:id" element={<RadiographDetail />} />
        </Route>
      </Route>
    </Routes>
  );
}
