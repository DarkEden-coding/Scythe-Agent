import { Message, ToolCall, FileEdit, Checkpoint, ContextItem, ReasoningBlock, Project } from '../types';

export const mockMessages: Message[] = [
  {
    id: 'msg-1',
    role: 'user',
    content: 'Create a React dashboard with a sidebar navigation and a main content area. Include charts for data visualization.',
    timestamp: new Date(Date.now() - 3600000),
    checkpointId: 'cp-1',
  },
  {
    id: 'msg-2',
    role: 'agent',
    content: "I'll create a React dashboard for you. Let me start by setting up the project structure and installing the necessary dependencies for charts.",
    timestamp: new Date(Date.now() - 3550000),
  },
  {
    id: 'msg-3',
    role: 'agent',
    content: "I've created the dashboard structure with:\n\n1. **Sidebar Navigation** - A collapsible sidebar with navigation links\n2. **Main Content Area** - A responsive grid layout\n3. **Charts** - Using Recharts for bar and line charts\n\nWould you like me to add any specific features or modify the styling?",
    timestamp: new Date(Date.now() - 3400000),
  },
  {
    id: 'msg-4',
    role: 'user',
    content: 'Add a dark mode toggle and make the sidebar collapsible with smooth animations.',
    timestamp: new Date(Date.now() - 2800000),
    checkpointId: 'cp-2',
  },
  {
    id: 'msg-5',
    role: 'agent',
    content: "Great! I'll add dark mode support and enhance the sidebar with collapse functionality and smooth CSS transitions.",
    timestamp: new Date(Date.now() - 2750000),
  },
  {
    id: 'msg-6',
    role: 'agent',
    content: "Done! I've implemented:\n\n- **Dark Mode Toggle** - Persists to localStorage\n- **Collapsible Sidebar** - With 300ms transition animations\n- **Icon-only mode** - When collapsed, shows only icons with tooltips\n\nThe theme automatically syncs with the system preference on first load.",
    timestamp: new Date(Date.now() - 2500000),
  },
  {
    id: 'msg-7',
    role: 'user',
    content: 'Can you add user authentication with a login page?',
    timestamp: new Date(Date.now() - 1800000),
    checkpointId: 'cp-3',
  },
  {
    id: 'msg-8',
    role: 'agent',
    content: "I'll set up authentication with a login page, protected routes, and session management. Let me create the auth components and context.",
    timestamp: new Date(Date.now() - 1750000),
  },
  {
    id: 'msg-9',
    role: 'agent',
    content: "Authentication is now set up! Here's what I added:\n\n- **Login Page** - Clean form with email/password validation\n- **Auth Context** - React context for managing auth state\n- **Protected Routes** - Redirects unauthenticated users\n- **Logout Button** - In the sidebar with confirmation\n\nFor demo purposes, any email/password combination works.",
    timestamp: new Date(Date.now() - 1400000),
  },
];

export const mockToolCalls: ToolCall[] = [
  {
    id: 'tc-1',
    name: 'read_file',
    status: 'completed',
    input: { path: 'package.json' },
    output: '{ "name": "dashboard", "version": "1.0.0" ... }',
    timestamp: new Date(Date.now() - 3540000),
    duration: 120,
  },
  {
    id: 'tc-2',
    name: 'install_npm_packages',
    status: 'completed',
    input: { packages: ['recharts', 'lucide-react', 'clsx'] },
    output: 'Successfully installed 3 packages',
    timestamp: new Date(Date.now() - 3530000),
    duration: 4500,
  },
  {
    id: 'tc-3',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/components/Sidebar.tsx', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 3500000),
    duration: 85,
    isParallel: true,
    parallelGroupId: 'pg-1',
  },
  {
    id: 'tc-4',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/components/Dashboard.tsx', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 3500000),
    duration: 92,
    isParallel: true,
    parallelGroupId: 'pg-1',
  },
  {
    id: 'tc-5',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/components/Charts.tsx', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 3500000),
    duration: 78,
    isParallel: true,
    parallelGroupId: 'pg-1',
  },
  {
    id: 'tc-6',
    name: 'edit_file',
    status: 'completed',
    input: { path: 'src/App.tsx', context: 'function App() {', replacement: '...' },
    output: 'Edit applied successfully',
    timestamp: new Date(Date.now() - 3450000),
    duration: 110,
  },
  {
    id: 'tc-7',
    name: 'build_project',
    status: 'completed',
    input: {},
    output: 'Build completed successfully in 2.3s',
    timestamp: new Date(Date.now() - 3420000),
    duration: 2300,
  },
  {
    id: 'tc-8',
    name: 'read_file',
    status: 'completed',
    input: { path: 'src/components/Sidebar.tsx' },
    output: 'export function Sidebar() { ... }',
    timestamp: new Date(Date.now() - 2740000),
    duration: 65,
  },
  {
    id: 'tc-9',
    name: 'edit_file',
    status: 'completed',
    input: { path: 'src/components/Sidebar.tsx', context: 'const [collapsed, setCollapsed]', replacement: '...' },
    output: 'Edit applied successfully',
    timestamp: new Date(Date.now() - 2700000),
    duration: 95,
    isParallel: true,
    parallelGroupId: 'pg-2',
  },
  {
    id: 'tc-10',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/hooks/useDarkMode.ts', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 2700000),
    duration: 72,
    isParallel: true,
    parallelGroupId: 'pg-2',
  },
  {
    id: 'tc-11',
    name: 'edit_file',
    status: 'completed',
    input: { path: 'src/index.css', context: '@tailwind', replacement: '...' },
    output: 'Edit applied successfully',
    timestamp: new Date(Date.now() - 2700000),
    duration: 55,
    isParallel: true,
    parallelGroupId: 'pg-2',
  },
  {
    id: 'tc-12',
    name: 'build_project',
    status: 'completed',
    input: {},
    output: 'Build completed successfully in 1.8s',
    timestamp: new Date(Date.now() - 2550000),
    duration: 1800,
  },
  {
    id: 'tc-13',
    name: 'list_files',
    status: 'completed',
    input: {},
    output: '["src/App.tsx", "src/components/...", ...]',
    timestamp: new Date(Date.now() - 1740000),
    duration: 45,
  },
  {
    id: 'tc-14',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/contexts/AuthContext.tsx', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 1700000),
    duration: 88,
    isParallel: true,
    parallelGroupId: 'pg-3',
  },
  {
    id: 'tc-15',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/pages/Login.tsx', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 1700000),
    duration: 102,
    isParallel: true,
    parallelGroupId: 'pg-3',
  },
  {
    id: 'tc-16',
    name: 'create_file',
    status: 'completed',
    input: { path: 'src/components/ProtectedRoute.tsx', content: '...' },
    output: 'File created successfully',
    timestamp: new Date(Date.now() - 1700000),
    duration: 67,
    isParallel: true,
    parallelGroupId: 'pg-3',
  },
  {
    id: 'tc-17',
    name: 'edit_file',
    status: 'completed',
    input: { path: 'src/App.tsx', context: '<BrowserRouter>', replacement: '...' },
    output: 'Edit applied successfully',
    timestamp: new Date(Date.now() - 1600000),
    duration: 125,
  },
  {
    id: 'tc-18',
    name: 'edit_file',
    status: 'completed',
    input: { path: 'src/components/Sidebar.tsx', context: '</nav>', replacement: '...' },
    output: 'Edit applied successfully',
    timestamp: new Date(Date.now() - 1550000),
    duration: 88,
  },
  {
    id: 'tc-19',
    name: 'build_project',
    status: 'completed',
    input: {},
    output: 'Build completed successfully in 2.1s',
    timestamp: new Date(Date.now() - 1450000),
    duration: 2100,
  },
];

export const mockFileEdits: FileEdit[] = [
  {
    id: 'fe-1',
    filePath: 'src/components/Sidebar.tsx',
    action: 'create',
    diff: `  import { useState } from 'react';
  import { Home, Settings, Users, BarChart3 } from 'lucide-react';
  
  interface NavItem {
    icon: React.ReactNode;
    label: string;
    href: string;
  }
  
  export function Sidebar() {
    const [active, setActive] = useState('dashboard');
    const navItems: NavItem[] = [
      { icon: <Home />, label: 'Dashboard', href: '/dashboard' },
      { icon: <BarChart3 />, label: 'Analytics', href: '/analytics' },
      { icon: <Users />, label: 'Users', href: '/users' },
      { icon: <Settings />, label: 'Settings', href: '/settings' },
    ];
    return (
      <aside className="w-64 bg-gray-900 border-r border-gray-800">
        {navItems.map(item => (
          <NavLink key={item.href} item={item} active={active} />
        ))}
      </aside>
    );
  }`,
    timestamp: new Date(Date.now() - 3500000),
    checkpointId: 'cp-1',
  },
  {
    id: 'fe-2',
    filePath: 'src/components/Dashboard.tsx',
    action: 'create',
    diff: `  import { StatsCard } from './StatsCard';
  import { ChartSection } from './ChartSection';
  
  export function Dashboard() {
    return (
      <main className="flex-1 p-6">
        <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatsCard title="Revenue" value="$45,231" />
          <StatsCard title="Users" value="2,350" />
          <StatsCard title="Orders" value="1,247" />
          <StatsCard title="Growth" value="+12.5%" />
        </div>
        <ChartSection />
      </main>
    );
  }`,
    timestamp: new Date(Date.now() - 3500000),
    checkpointId: 'cp-1',
  },
  {
    id: 'fe-3',
    filePath: 'src/components/Charts.tsx',
    action: 'create',
    diff: `  import { BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts';
  
  const data = [
    { name: 'Jan', value: 400 },
    { name: 'Feb', value: 300 },
    { name: 'Mar', value: 600 },
    { name: 'Apr', value: 800 },
  ];
  
  export function Charts() {
    return (
      <BarChart width={600} height={300} data={data}>
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="value" fill="#22d3d8" />
      </BarChart>
    );
  }`,
    timestamp: new Date(Date.now() - 3500000),
    checkpointId: 'cp-1',
  },
  {
    id: 'fe-4',
    filePath: 'src/App.tsx',
    action: 'edit',
    diff: `- import './App.css';
- 
- function App() {
-   return <div>Hello World</div>;
- }
+ import { Sidebar } from "./components/Sidebar";
+ import { Dashboard } from "./components/Dashboard";
+ import { Charts } from "./components/Charts";
+ 
+ function App() {
+   return (
+     <div className="flex h-screen bg-gray-950">
+       <Sidebar />
+       <Dashboard />
+     </div>
+   );
+ }`,
    timestamp: new Date(Date.now() - 3450000),
    checkpointId: 'cp-1',
  },
  {
    id: 'fe-5',
    filePath: 'src/components/Sidebar.tsx',
    action: 'edit',
    diff: `  export function Sidebar() {
-   const [active, setActive] = useState('dashboard');
+   const [active, setActive] = useState('dashboard');
+   const [collapsed, setCollapsed] = useState(false);
+ 
    const navItems: NavItem[] = [
      ...
    ];
    return (
-     <aside className="w-64 bg-gray-900 border-r">
+     <aside className={\`\${collapsed ? 'w-16' : 'w-64'} bg-gray-900 border-r transition-all duration-300\`}>
+       <button onClick={() => setCollapsed(!collapsed)}>
+         <ChevronLeft className={\`transform \${collapsed ? 'rotate-180' : ''}\`} />
+       </button>
        {navItems.map(item => (
-         <NavLink key={item.href} item={item} active={active} />
+         <NavLink key={item.href} item={item} active={active} collapsed={collapsed} />
        ))}
      </aside>
    );
  }`,
    timestamp: new Date(Date.now() - 2700000),
    checkpointId: 'cp-2',
  },
  {
    id: 'fe-6',
    filePath: 'src/hooks/useDarkMode.ts',
    action: 'create',
    diff: `  import { useState, useEffect } from 'react';
  
  export function useDarkMode() {
    const [isDark, setIsDark] = useState(() => {
      const saved = localStorage.getItem('darkMode');
      if (saved !== null) return JSON.parse(saved);
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    });
  
    useEffect(() => {
      localStorage.setItem('darkMode', JSON.stringify(isDark));
      document.documentElement.classList.toggle('dark', isDark);
    }, [isDark]);
  
    return [isDark, setIsDark] as const;
  }`,
    timestamp: new Date(Date.now() - 2700000),
    checkpointId: 'cp-2',
  },
  {
    id: 'fe-7',
    filePath: 'src/index.css',
    action: 'edit',
    diff: `  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  
+ :root {
+   --bg-primary: #ffffff;
+   --bg-secondary: #f8fafc;
+   --text-primary: #0f172a;
+ }
+ 
+ .dark {
+   --bg-primary: #0f172a;
+   --bg-secondary: #1e293b;
+   --text-primary: #f8fafc;
+ }
+ 
+ body {
+   background: var(--bg-primary);
+   color: var(--text-primary);
+   transition: background 300ms, color 300ms;
+ }`,
    timestamp: new Date(Date.now() - 2700000),
    checkpointId: 'cp-2',
  },
  {
    id: 'fe-8',
    filePath: 'src/contexts/AuthContext.tsx',
    action: 'create',
    diff: `  import { createContext, useContext, useState, ReactNode } from 'react';
  
  interface AuthContextType {
    user: User | null;
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
    isAuthenticated: boolean;
  }
  
  const AuthContext = createContext<AuthContextType | null>(null);
  
  export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
  
    const login = async (email: string, password: string) => {
      // Demo: accept any credentials
      setUser({ id: '1', email, name: email.split('@')[0] });
    };
  
    const logout = () => setUser(null);
  
    return (
      <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
        {children}
      </AuthContext.Provider>
    );
  }
  
  export const useAuth = () => useContext(AuthContext)!;`,
    timestamp: new Date(Date.now() - 1700000),
    checkpointId: 'cp-3',
  },
  {
    id: 'fe-9',
    filePath: 'src/pages/Login.tsx',
    action: 'create',
    diff: `  import { useState } from 'react';
  import { useAuth } from '../contexts/AuthContext';
  
  export function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const { login } = useAuth();
  
    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      await login(email, password);
    };
  
    return (
      <div className="min-h-screen flex items-center justify-center">
        <form onSubmit={handleSubmit} className="w-96 p-8 rounded-xl">
          <h2 className="text-2xl font-bold mb-6">Sign In</h2>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} />
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
          <button type="submit">Sign In</button>
        </form>
      </div>
    );
  }`,
    timestamp: new Date(Date.now() - 1700000),
    checkpointId: 'cp-3',
  },
  {
    id: 'fe-10',
    filePath: 'src/components/ProtectedRoute.tsx',
    action: 'create',
    diff: `  import { Navigate } from 'react-router-dom';
  import { useAuth } from '../contexts/AuthContext';
  
  export function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated } = useAuth();
    if (!isAuthenticated) return <Navigate to="/login" replace />;
    return <>{children}</>;
  }`,
    timestamp: new Date(Date.now() - 1700000),
    checkpointId: 'cp-3',
  },
  {
    id: 'fe-11',
    filePath: 'src/App.tsx',
    action: 'edit',
    diff: `  import { Sidebar } from "./components/Sidebar";
  import { Dashboard } from "./components/Dashboard";
+ import { AuthProvider } from "./contexts/AuthContext";
+ import { ProtectedRoute } from "./components/ProtectedRoute";
+ import { Login } from "./pages/Login";
+ import { BrowserRouter, Routes, Route } from "react-router-dom";
  
  function App() {
    return (
-     <div className="flex h-screen bg-gray-950">
-       <Sidebar />
-       <Dashboard />
-     </div>
+     <AuthProvider>
+       <BrowserRouter>
+         <Routes>
+           <Route path="/login" element={<Login />} />
+           <Route path="/*" element={
+             <ProtectedRoute>
+               <div className="flex h-screen bg-gray-950">
+                 <Sidebar />
+                 <Dashboard />
+               </div>
+             </ProtectedRoute>
+           } />
+         </Routes>
+       </BrowserRouter>
+     </AuthProvider>
    );
  }`,
    timestamp: new Date(Date.now() - 1600000),
    checkpointId: 'cp-3',
  },
  {
    id: 'fe-12',
    filePath: 'src/components/Sidebar.tsx',
    action: 'edit',
    diff: `  import { Home, Settings, Users, BarChart3 } from 'lucide-react';
+ import { LogOut } from 'lucide-react';
+ import { useAuth } from '../contexts/AuthContext';
  
  ...
  
+       <div className="mt-auto p-4 border-t border-gray-800">
+         <button
+           onClick={logout}
+           className="flex items-center gap-2 text-gray-400 hover:text-red-400"
+         >
+           <LogOut className="w-4 h-4" />
+           {!collapsed && <span>Logout</span>}
+         </button>
+       </div>
      </aside>
    );
  }`,
    timestamp: new Date(Date.now() - 1550000),
    checkpointId: 'cp-3',
  },
];

export const mockCheckpoints: Checkpoint[] = [
  {
    id: 'cp-1',
    messageId: 'msg-1',
    timestamp: new Date(Date.now() - 3600000),
    label: 'Initial dashboard setup',
    fileEdits: ['fe-1', 'fe-2', 'fe-3', 'fe-4'],
    toolCalls: ['tc-1', 'tc-2', 'tc-3', 'tc-4', 'tc-5', 'tc-6', 'tc-7'],
    reasoningBlocks: ['rb-1'],
  },
  {
    id: 'cp-2',
    messageId: 'msg-4',
    timestamp: new Date(Date.now() - 2800000),
    label: 'Dark mode & collapsible sidebar',
    fileEdits: ['fe-5', 'fe-6', 'fe-7'],
    toolCalls: ['tc-8', 'tc-9', 'tc-10', 'tc-11', 'tc-12'],
    reasoningBlocks: ['rb-2'],
  },
  {
    id: 'cp-3',
    messageId: 'msg-7',
    timestamp: new Date(Date.now() - 1800000),
    label: 'Authentication system',
    fileEdits: ['fe-8', 'fe-9', 'fe-10', 'fe-11', 'fe-12'],
    toolCalls: ['tc-13', 'tc-14', 'tc-15', 'tc-16', 'tc-17', 'tc-18', 'tc-19'],
    reasoningBlocks: ['rb-3'],
  },
];

export const mockReasoningBlocks: ReasoningBlock[] = [
  {
    id: 'rb-1',
    content: `The user wants a React dashboard with sidebar navigation and charts. Let me think about the best approach:

1. I should first check the existing project structure by reading package.json
2. Install recharts for data visualization - it's the most popular React charting library
3. Install lucide-react for icons in the sidebar
4. Create the component structure:
   - Sidebar.tsx - navigation with icons and active state
   - Dashboard.tsx - main content area with stats cards grid
   - Charts.tsx - recharts bar chart component
5. Update App.tsx to compose these together in a flex layout

I'll create the sidebar, dashboard, and charts components in parallel since they're independent. Then I'll wire them together in App.tsx.`,
    timestamp: new Date(Date.now() - 3545000),
    duration: 3200,
    checkpointId: 'cp-1',
  },
  {
    id: 'rb-2',
    content: `The user wants dark mode toggle and collapsible sidebar with smooth animations. Let me plan:

For the collapsible sidebar:
- Add a collapsed state boolean
- Use CSS transition on width (w-64 → w-16)
- When collapsed, show only icons with tooltips
- Add a toggle button with a chevron that rotates

For dark mode:
- Create a useDarkMode hook that persists to localStorage
- Check system preference on first load with matchMedia
- Toggle a 'dark' class on document.documentElement
- Add CSS variables for theme colors
- Use transition on background and color for smooth switching

I can do the sidebar edit, dark mode hook creation, and CSS updates in parallel since they're independent files. Then I'll need to build to verify.`,
    timestamp: new Date(Date.now() - 2745000),
    duration: 2100,
    checkpointId: 'cp-2',
  },
  {
    id: 'rb-3',
    content: `User wants authentication with a login page. This requires several interconnected pieces:

1. AuthContext - React context for managing auth state globally
   - Store user object (or null)
   - Provide login/logout functions
   - Expose isAuthenticated boolean

2. Login page - Clean form component
   - Email and password inputs with validation
   - Submit handler that calls auth context login
   - For demo purposes, accept any credentials

3. ProtectedRoute wrapper component
   - Check isAuthenticated from context
   - Redirect to /login if not authenticated
   - Render children if authenticated

4. Need to update App.tsx to:
   - Wrap everything in AuthProvider
   - Add BrowserRouter and Routes
   - Add login route
   - Wrap dashboard routes in ProtectedRoute

5. Add logout button to Sidebar
   - Import LogOut icon
   - Add button at bottom of sidebar
   - Call logout from auth context

I'll create AuthContext, Login, and ProtectedRoute in parallel, then update App.tsx and Sidebar sequentially since they depend on the new files.`,
    timestamp: new Date(Date.now() - 1745000),
    duration: 4500,
    checkpointId: 'cp-3',
  },
];

export const mockContextItems: ContextItem[] = [
  { id: 'ctx-1', type: 'file', name: 'src/App.tsx', tokens: 850 },
  { id: 'ctx-2', type: 'file', name: 'src/components/Sidebar.tsx', tokens: 1240 },
  { id: 'ctx-3', type: 'file', name: 'src/components/Dashboard.tsx', tokens: 980 },
  { id: 'ctx-4', type: 'file', name: 'src/components/Charts.tsx', tokens: 1560 },
  { id: 'ctx-5', type: 'file', name: 'src/hooks/useDarkMode.ts', tokens: 420 },
  { id: 'ctx-6', type: 'file', name: 'src/contexts/AuthContext.tsx', tokens: 890 },
  { id: 'ctx-7', type: 'file', name: 'src/pages/Login.tsx', tokens: 720 },
  { id: 'ctx-8', type: 'file', name: 'src/components/ProtectedRoute.tsx', tokens: 340 },
  { id: 'ctx-9', type: 'conversation', name: 'Chat History', tokens: 2450 },
  { id: 'ctx-10', type: 'tool_output', name: 'build_project output', tokens: 180 },
  { id: 'ctx-11', type: 'tool_output', name: 'list_files output', tokens: 320 },
  { id: 'ctx-12', type: 'summary', name: 'Previous context summary', tokens: 1200 },
];

export const mockProjects: Project[] = [
  {
    id: 'proj-1',
    name: 'dashboard-app',
    path: '~/projects/dashboard-app',
    lastAccessed: new Date(Date.now() - 600000),
    isExpanded: true,
    chats: [
      {
        id: 'chat-1',
        title: 'Build React dashboard with charts',
        lastMessage: 'Authentication is now set up!',
        timestamp: new Date(Date.now() - 1400000),
        messageCount: 9,
        isActive: true,
      },
      {
        id: 'chat-2',
        title: 'Fix responsive layout issues',
        lastMessage: 'All breakpoints are now working correctly.',
        timestamp: new Date(Date.now() - 86400000),
        messageCount: 5,
      },
      {
        id: 'chat-3',
        title: 'Add data export feature',
        lastMessage: 'CSV and PDF export both working.',
        timestamp: new Date(Date.now() - 172800000),
        messageCount: 12,
      },
    ],
  },
  {
    id: 'proj-2',
    name: 'api-gateway',
    path: '~/projects/api-gateway',
    lastAccessed: new Date(Date.now() - 7200000),
    isExpanded: false,
    chats: [
      {
        id: 'chat-4',
        title: 'Set up Express middleware',
        lastMessage: 'Rate limiting and CORS configured.',
        timestamp: new Date(Date.now() - 7200000),
        messageCount: 8,
      },
      {
        id: 'chat-5',
        title: 'Add JWT authentication',
        lastMessage: 'Token refresh flow is complete.',
        timestamp: new Date(Date.now() - 259200000),
        messageCount: 15,
      },
      {
        id: 'chat-6',
        title: 'Database migration scripts',
        lastMessage: 'All migrations run successfully.',
        timestamp: new Date(Date.now() - 345600000),
        messageCount: 6,
      },
      {
        id: 'chat-7',
        title: 'WebSocket event handlers',
        lastMessage: 'Real-time notifications working.',
        timestamp: new Date(Date.now() - 432000000),
        messageCount: 11,
      },
    ],
  },
  {
    id: 'proj-3',
    name: 'mobile-app',
    path: '~/projects/mobile-app',
    lastAccessed: new Date(Date.now() - 43200000),
    isExpanded: false,
    chats: [
      {
        id: 'chat-8',
        title: 'React Native navigation setup',
        lastMessage: 'Stack and tab navigators configured.',
        timestamp: new Date(Date.now() - 43200000),
        messageCount: 7,
      },
      {
        id: 'chat-9',
        title: 'Push notification integration',
        lastMessage: 'FCM tokens are being stored correctly.',
        timestamp: new Date(Date.now() - 518400000),
        messageCount: 9,
      },
    ],
  },
  {
    id: 'proj-4',
    name: 'design-system',
    path: '~/projects/design-system',
    lastAccessed: new Date(Date.now() - 604800000),
    isExpanded: false,
    chats: [
      {
        id: 'chat-10',
        title: 'Button component variants',
        lastMessage: 'All 12 variants documented in Storybook.',
        timestamp: new Date(Date.now() - 604800000),
        messageCount: 14,
      },
      {
        id: 'chat-11',
        title: 'Color token system',
        lastMessage: 'Semantic tokens mapped to primitives.',
        timestamp: new Date(Date.now() - 691200000),
        messageCount: 4,
      },
      {
        id: 'chat-12',
        title: 'Form input components',
        lastMessage: 'Validation states and error messages done.',
        timestamp: new Date(Date.now() - 777600000),
        messageCount: 18,
      },
    ],
  },
  {
    id: 'proj-5',
    name: 'ml-pipeline',
    path: '~/dev/ml-pipeline',
    lastAccessed: new Date(Date.now() - 1209600000),
    isExpanded: false,
    chats: [
      {
        id: 'chat-13',
        title: 'Data preprocessing scripts',
        lastMessage: 'Pipeline handles missing values now.',
        timestamp: new Date(Date.now() - 1209600000),
        messageCount: 22,
      },
      {
        id: 'chat-14',
        title: 'Model training configuration',
        lastMessage: 'Hyperparameter sweep complete.',
        timestamp: new Date(Date.now() - 1296000000),
        messageCount: 10,
      },
    ],
  },
  {
    id: 'proj-6',
    name: 'docs-site',
    path: '~/projects/docs-site',
    lastAccessed: new Date(Date.now() - 2592000000),
    isExpanded: false,
    chats: [
      {
        id: 'chat-15',
        title: 'MDX blog setup',
        lastMessage: 'Blog posts render with syntax highlighting.',
        timestamp: new Date(Date.now() - 2592000000),
        messageCount: 6,
      },
    ],
  },
];
