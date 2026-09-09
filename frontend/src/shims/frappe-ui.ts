import type { DefineComponent, Plugin } from "vue";

type InvestorCallParams = Record<string, unknown> | undefined;
type InvestorCallError = { type?: unknown; message?: unknown } | null;

export interface InvestorCall<TResponse, TParams extends InvestorCallParams = undefined> {
	error: InvestorCallError;
	submit: (params?: TParams) => Promise<TResponse | null>;
}

export declare function useCall<
	TResponse,
	TParams extends InvestorCallParams = undefined,
>(options: {
	url: string;
	immediate?: boolean;
	method?: "GET" | "POST" | "PUT" | "DELETE";
}): InvestorCall<TResponse, TParams>;

export declare const Button: DefineComponent<any>;
export declare const Avatar: DefineComponent<any>;
export declare const Badge: DefineComponent<any>;
export declare const Checkbox: DefineComponent<any>;
export declare const FormControl: DefineComponent<any>;
export declare const Icon: DefineComponent<any>;
export declare const Select: DefineComponent<any>;
export declare const FrappeUI: Plugin;
