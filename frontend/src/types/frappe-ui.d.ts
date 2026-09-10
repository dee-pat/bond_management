import type { DefineComponent } from "vue";

import type { AvatarProps } from "../../node_modules/frappe-ui/src/components/Avatar/types";
import type { BadgeProps } from "../../node_modules/frappe-ui/src/components/Badge/types";
import type { BreadcrumbsProps } from "../../node_modules/frappe-ui/src/components/Breadcrumbs/types";
import type { ButtonProps } from "../../node_modules/frappe-ui/src/components/Button/types";
import type { CheckboxProps } from "../../node_modules/frappe-ui/src/components/Checkbox/types";
import type { DesktopShellProps } from "../../node_modules/frappe-ui/src/components/DesktopShell/types";
import type { ErrorMessageProps } from "../../node_modules/frappe-ui/src/components/ErrorMessage/types";
import type { FormControlProps } from "../../node_modules/frappe-ui/src/components/FormControl/types";
import type { IconProps } from "../../node_modules/frappe-ui/src/components/Icon/types";
import type { LoadingTextProps } from "../../node_modules/frappe-ui/src/components/LoadingText/types";
import type {
	MobileNavItemProps,
	MobileNavProps,
} from "../../node_modules/frappe-ui/src/components/MobileNav/types";
import type { MobileShellProps } from "../../node_modules/frappe-ui/src/components/MobileShell/types";
import type { PageHeaderMobileProps } from "../../node_modules/frappe-ui/src/components/PageHeader/types";
import type { ScrollAreaProps } from "../../node_modules/frappe-ui/src/components/ScrollArea/types";
import type { SelectProps } from "../../node_modules/frappe-ui/src/components/Select/types";
import type {
	SidebarHeaderProps,
	SidebarItemProps,
	SidebarLabelProps,
	SidebarProps,
} from "../../node_modules/frappe-ui/src/components/Sidebar/types";

/**
 * beta.42 publishes its source barrel as the `types` entry. Keeping this
 * boundary on the package's prop contracts avoids checking unrelated optional
 * package internals while preserving strict props and named exports here.
 */
type FormControlPublicProps = FormControlProps & {
	modelValue?: string | number;
	options?: SelectProps["options"];
};

export { default as FrappeUI } from "../../node_modules/frappe-ui/src/utils/plugin";
export { useCall } from "../../node_modules/frappe-ui/src/data-fetching/useCall/useCall";

export declare const Avatar: DefineComponent<AvatarProps>;
export declare const Badge: DefineComponent<BadgeProps>;
export declare const Breadcrumbs: DefineComponent<BreadcrumbsProps>;
export declare const Button: DefineComponent<ButtonProps>;
export declare const DesktopShell: DefineComponent<DesktopShellProps>;
export declare const Checkbox: DefineComponent<CheckboxProps>;
export declare const ErrorMessage: DefineComponent<ErrorMessageProps>;
export declare const FormControl: DefineComponent<FormControlPublicProps>;
export declare const Icon: DefineComponent<IconProps>;
export declare const LoadingText: DefineComponent<LoadingTextProps>;
export declare const MobileNav: DefineComponent<MobileNavProps>;
export declare const MobileNavItem: DefineComponent<MobileNavItemProps>;
export declare const MobileShell: DefineComponent<MobileShellProps>;
export declare const PageHeader: DefineComponent<Record<never, never>>;
export declare const PageHeaderMobile: DefineComponent<PageHeaderMobileProps>;
export declare const ScrollArea: DefineComponent<ScrollAreaProps>;
export declare const Select: DefineComponent<SelectProps>;
export declare const Sidebar: DefineComponent<SidebarProps>;
export declare const SidebarHeader: DefineComponent<SidebarHeaderProps>;
export declare const SidebarItem: DefineComponent<SidebarItemProps>;
export declare const SidebarLabel: DefineComponent<SidebarLabelProps>;
